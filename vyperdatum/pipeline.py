import logging
from typing import Union, Optional
from colorama import Fore, Style
from itertools import islice
import pyproj as pp
import networkx as nx
from tqdm import tqdm
from vyperdatum.db import DB
from vyperdatum.utils.crs_utils import validate_transform_steps, auth_code

logger = logging.getLogger("root_logger")


class Pipeline():
    """
    Requirements:
    source and target CRS must have explicit code in database
    (not any custom-built compound CRS will work).

    Assumes:
    Both source and target crs's horizontal crs are 3d (note the `.to_3d()` transforms)
    """
    def __init__(self,
                 crs_from: Union[pp.CRS, int, str],
                 crs_to: Union[pp.CRS, int, str],
                 filters: Optional[list[str]] = None
                 ) -> None:
        """

        Parameters
        ----------
        crs_from: pyproj.crs.CRS or input used to create one
            Projection of input data.
        crs_to: pyproj.crs.CRS or input used to create one
            Projection of output data.
        filters: list[str], optional, default=None
            WHERE clause conditions to filter the transformers in the db's
            `coordinate_operation_view`. If more than one condition is passed,
            logical `AND` is applied. Example: `filters=["auth_name='NOAA'"]`.
            Only applicable to the graph-based algorithm.

        Raises
        -------
        ValueError:
            If either code or authority of `crs_from`/`crs_to` (or their sub_crs)
            can not be determined. A compound CRS must have explicit auth/code in the database.

        """
        self.steps, self.head, self.tail = [], [], []
        self.G, self.nodes = None, []
        self.filters = filters
        self.WEIGHT = 1
        if not isinstance(crs_from, pp.CRS):
            crs_from = pp.CRS(crs_from)
        if not isinstance(crs_to, pp.CRS):
            crs_to = pp.CRS(crs_to)
        self.crs_from = crs_from
        self.crs_to = crs_to

        if self.crs_from.is_projected:
            self.head = [auth_code(self.crs_from, raise_no_auth=False)]
            if self.crs_from.is_compound:
                h = auth_code(pp.CRS(self.crs_from.sub_crs_list[0]).geodetic_crs)
                v = auth_code(pp.CRS(self.crs_from.sub_crs_list[1]))
                self.crs_from = pp.CRS(f"{h}+{v}")
            else:
                if self.crs_from.geodetic_crs.to_3d().to_authority():
                    self.crs_from = pp.CRS(auth_code(self.crs_from.geodetic_crs.to_3d()))
                else:
                    self.crs_from = pp.CRS(auth_code(self.crs_from.geodetic_crs))

        if self.crs_to.is_projected:
            self.tail = [auth_code(self.crs_to, raise_no_auth=False)]
            if self.crs_to.is_compound:
                h = auth_code(pp.CRS(self.crs_to.sub_crs_list[0]).geodetic_crs)
                v = auth_code(pp.CRS(self.crs_to.sub_crs_list[1]))
                self.crs_to = pp.CRS(f"{h}+{v}")
            else:
                if self.crs_to.geodetic_crs.to_3d().to_authority():
                    self.crs_to = pp.CRS(auth_code(self.crs_to.geodetic_crs.to_3d()))
                else:
                    self.crs_to = pp.CRS(auth_code(self.crs_to.geodetic_crs))

        self.s_h, self.s_v = self.split_crs(self.crs_from)
        self.t_h, self.t_v = self.split_crs(self.crs_to)
        self.crs_from = auth_code(self.crs_from)
        self.crs_to = auth_code(self.crs_to)
        self._compatible_h_for_v()
        return

    def _compatible_h_for_v(self) -> None:
        """
        Check if the horizontal CRS used for the compound output CRS is compatible with
        the vertical CRS. If not, replace with a valid horizontal CRS and prepend the original
        compound CRS to the tail list. The input horizontal and vertical CRSs are expected to
        be compatible already.

        Raises
        -------
        ValueError:
            When there is no matching horizontal CRS for the vertical component of the
            output CRS.
        """
        if pp.CRS(self.crs_to).is_compound:
            _, s_v = self.split_crs(pp.CRS(self.crs_from))
            h, v = self.split_crs(pp.CRS(self.crs_to))
            if s_v.upper() == v.upper():
                return
            va, vc = v.split(":")
            df = DB().query("select concat(horiz_crs_auth_name, ':', horiz_crs_code) hac from"
                            f" compound_crs where vertical_crs_auth_name='{va}'"
                            f" and vertical_crs_code='{vc}'", dataframe=True
                            )
            if h not in df["hac"].values:
                s_h = ":".join(pp.CRS(self.crs_from).geodetic_crs.to_2d().to_authority())
                if len(df) == 1:
                    compatible_h = df['hac'].values[0]
                elif s_h in df["hac"].values:
                    compatible_h = s_h
                else:
                    raise ValueError(f"{Fore.RED}Unable to find a matching output horizontal CRS"
                                     f"  for {v}.The followings are potential compatible"
                                     f" horizontal CRSs for {v}:\n{df['hac']}")
                self.tail = [self.crs_to] + self.tail
                self.crs_to = auth_code(f"{compatible_h}+{v}")
                self.t_h, self.t_v = compatible_h, v
        return

    @staticmethod
    def split_crs(crs: pp.CRS) -> tuple[str, Optional[str]]:
        """
        Return CRS string representation in form of code:authority

        Raises
        -------
        ValueError:
            If vertical-only CRS is received.

        Returns
        --------
        tuple:
            crs components in form of code:authority
        """
        if crs.is_vertical and not crs.is_compound:
            raise ValueError(f"The pipeline doesn't accept vertical-only crs:\n{crs}")
        h = ":".join(crs.geodetic_crs.to_authority(min_confidence=100))
        v = None
        if crs.is_compound:
            v = ":".join(pp.CRS(crs.sub_crs_list[1]).to_authority(min_confidence=100))
        return h, v

    @staticmethod
    def join_crs(h_crs: str, v_crs: str) -> str:
        """
        Return CRS string representation in form of code:authority

        Raises
        -------
        ValueError:
            If horizontal CRS is None; or when the CRS is invalid.

        Returns
        --------
        str:
            Concatenate the horizontal and vertical (if exists) CRS components using a `+` sign.
        """
        if not h_crs:
            raise ValueError("The horizontal CRS must be set.")
        try:
            _crs = f"{h_crs}{'+' + v_crs if v_crs else ''}"
            pp.CRS(_crs)
        except Exception as e:
            logger.exception(f"Unable to build crs: {_crs}\n{e}")
        return _crs

    def linear_steps(self) -> Optional[list[str]]:
        """
        Return a list of CRSs representing the transformation steps from `crs_from` to `crs_to`.
        If the generated pipeline can't be validated by PROJ, return `None`.
        """
        self.steps = []
        if f"{self.s_h}+{self.s_v}" == f"{self.t_h}+{self.t_v}":
            return []
        self.steps.append(self.join_crs(self.s_h, self.s_v))
        while (self.join_crs(*self.split_crs(pp.CRS(self.steps[-1])))
               !=
               self.join_crs(self.t_h, self.t_v)
               ):
            _, cur_v = self.split_crs(pp.CRS(self.steps[-1]))
            cur_h = ":".join(pp.CRS(self.steps[-1]).geodetic_crs.to_2d().to_authority())
            t_h = ":".join(pp.CRS(self.crs_to).geodetic_crs.to_2d().to_authority())
            if cur_h == t_h:
                self.steps.append(self.join_crs(t_h, self.t_v))
            else:
                if cur_h in ("EPSG:6318", "EPSG:4326") and t_h in ("EPSG:6318", "EPSG:4326"):
                    self.steps.append(self.join_crs("EPSG:9755", cur_v))
                if (cur_v is None and
                    pp.CRS(t_h).geodetic_crs.to_3d() and
                    (pp.CRS(self.crs_to).is_compound or len(pp.CRS(self.crs_to).axis_info) > 2)
                    ):  # noqa: E125
                    self.steps.append(":".join(pp.CRS(t_h).geodetic_crs.to_3d().to_authority()))
                else:
                    self.steps.append(self.join_crs(t_h, cur_v))
        temp_steps = self.head + self.steps + self.tail
        if not validate_transform_steps(temp_steps):
            logger.error(f"{Fore.RED}The following transformation steps generated using the"
                         f" linear algorithm: {temp_steps}, but PROJ cannot instantiate"
                         " valid transformer objects using them.")
            print(Style.RESET_ALL)
            return None
        self.steps = temp_steps
        return self.steps

    def build_graph(self):
        """
        Construct a graph model of the transformers defined in the proj.db.
        """
        self.G = nx.DiGraph()
        where_clause = "where deprecated=0"
        if self.filters:
            where_clause += " and " + " and ".join(self.filters)
        sql = f"select * from coordinate_operation_view {where_clause}"
        df = DB().query(sql, dataframe=True)
        logger.info("Building the transformer graph ...")
        for _, row in tqdm(df.iterrows(), total=df.shape[0]):
            self.G.add_edge(f"{row['source_crs_auth_name']}:{row['source_crs_code']}",
                            f"{row['target_crs_auth_name']}:{row['target_crs_code']}",
                            weight=self.WEIGHT
                            )
        self.add_extensions()
        return

    def _add_edge(self, node1, node2, weight, bidirectional=False):
        if not self.G.has_edge(node1, node2):
            self.G.add_edge(node1, node2, weight=weight)
        if bidirectional and not self.G.has_edge(node2, node1):
            self.G.add_edge(node2, node1, weight=weight)
        return

    def _remove_edge(self, node1, node2, bidirectional=False):
        if self.G.has_edge(node1, node2):
            self.G.remove_edge(node1, node2)
        if bidirectional and self.G.has_edge(node2, node1):
            self.G.remove_edge(node2, node1)
        return

    def add_extensions(self):
        """
        Add known valid transformation edges that are not explicitly listed in the database.
        Remove some of the known incorrect transformers in the database.
        """
        self._add_edge("EPSG:6319", "EPSG:7912", weight=self.WEIGHT, bidirectional=True)

        self._remove_edge("EPSG:4326", "EPSG:6318", bidirectional=True)
        self._add_edge("EPSG:4326", "EPSG:9755", weight=self.WEIGHT/10, bidirectional=True)
        self._add_edge("EPSG:9755", "EPSG:6318", weight=self.WEIGHT/10, bidirectional=True)

        self._add_edge("EPSG:4979", "EPSG:4269", weight=self.WEIGHT, bidirectional=True)
        self._add_edge("EPSG:4269", "EPSG:6319", weight=self.WEIGHT, bidirectional=True)
        self._add_edge("EPSG:4269", "EPSG:6318", weight=self.WEIGHT, bidirectional=True)
        return

    def add_node(self, new_node: str):
        nodes = list(self.G.nodes())
        if new_node in nodes:
            return
        logger.info(f"Adding node {new_node} to the transformers graph ...")
        new_crs = pp.CRS(new_node)
        for n in tqdm(nodes):
            try:
                t1 = pp.Transformer.from_crs(crs_from=new_crs,
                                             crs_to=pp.CRS(n),
                                             allow_ballpark=False,
                                             only_best=True
                                             )
                ps = t1.to_proj4()
                if ps and "+proj=noop" not in ps and "Error" not in ps:
                    self.G.add_edge(new_node, n, weight=self.WEIGHT)
            except:  # noqa: E722
                pass

            try:
                t2 = pp.Transformer.from_crs(crs_from=pp.CRS(n),
                                             crs_to=new_crs,
                                             allow_ballpark=False,
                                             only_best=True
                                             )
                ps = t2.to_proj4()
                if ps and "+proj=noop" not in ps and "Error" not in ps:
                    self.G.add_edge(n, new_node, weight=self.WEIGHT)
            except:  # noqa: E722
                pass
        return

    def k_graph_steps(self, k, weight="weight"):
        """
        Return `k` shortest (optimal) transformation steps between the source and
        target CRSs, ordered by `weight`.
        """
        if not self.G:
            self.build_graph()
            self.add_node(auth_code(self.crs_from))
            self.add_node(auth_code(self.crs_to))
        paths = list(islice(nx.shortest_simple_paths(self.G,
                                                     self.crs_from,
                                                     self.crs_to,
                                                     weight=weight), k))
        return [self.head + p + self.tail for p in paths]

    def graph_steps(self, weight="weight") -> Optional[list[str]]:
        """
        Return the optimal (shortest path) transformation steps between the source and target
        CRSs, measured by `weight`.
        """
        if not self.G:
            self.build_graph()
            self.add_node(auth_code(self.crs_from))
            self.add_node(auth_code(self.crs_to))
        temp_steps = self.head + nx.shortest_path(self.G,
                                                  self.crs_from,
                                                  self.crs_to,
                                                  weight=weight) + self.tail
        if not validate_transform_steps(temp_steps):
            logger.error(f"{Fore.RED}The following transformation steps generated using the"
                         f" graph-based optimal path algorithm: {temp_steps}, but PROJ cannot"
                         " instantiate valid transformer objects using them.")
            print(Style.RESET_ALL)
            return None
        self.steps = temp_steps
        return self.steps


if __name__ == "__main__":
    # ! Error: noop, Invalid transformation step: EPSG:4326 --> EPSG:9755
    # crs_from, crs_to = "EPSG:4326", "EPSG:6318"

    # # !? PRVD  >>> Error: incompatible horizontal CRSs
    # crs_from, crs_to = "EPSG:26919+NOAA:5535", "EPSG:26919+EPSG:6641"
    # # EPSG:26919+NOAA:5535
    # # EPSG:6318+NOAA:5535
    # # EPSG:6318+EPSG:6641
    # # EPSG:26919+EPSG:6641
    # # graph: ['EPSG:26919+NOAA:5535', 'EPSG:4269+NOAA:5535', 'EPSG:4269+EPSG:6641', 'EPSG:26919+EPSG:6641']


    # # !? NY / CT
    # crs_from, crs_to = "EPSG:26919", "EPSG:26919+NOAA:5434"
    # # EPSG:26919
    # # EPSG:6319
    # # EPSG:6318+NOAA:5434
    # # EPSG:26919+NOAA:5434
    # # linear: ['EPSG:26919', 'EPSG:4269', 'EPSG:6319', 'EPSG:6318+NOAA:5434', 'EPSG:4269+NOAA:5434', 'EPSG:26919+NOAA:5434']
    # # graph: ['EPSG:26919', 'EPSG:4269', 'EPSG:6319', 'NOAA:8436', 'EPSG:4269+NOAA:5434', 'EPSG:26919+NOAA:5434']


    # # ! should it go to 9755 (or equivalent) first?
    # crs_from, crs_to = "EPSG:32609", "EPSG:26909"
    # # linear: ['EPSG:32609', 'EPSG:4979', 'EPSG:4269', 'EPSG:26909'] 
    # # graph: ['EPSG:32609', 'EPSG:4979', 'EPSG:4269', 'EPSG:26909']



    # # ME/ MA
    # crs_from, crs_to = "EPSG:6348", "EPSG:6348+NOAA:5320"
    # # EPSG:6348
    # # EPSG:6319
    # # EPSG:6318+NOAA:5320
    # # EPSG:6348+NOAA:5320
    # # linear: ['EPSG:6348', 'EPSG:6319', 'EPSG:6318+NOAA:5320', 'EPSG:6348+NOAA:5320']
    # # graph: ['EPSG:6348', 'EPSG:6319', 'NOAA:8322', 'EPSG:6348+NOAA:5320']

    # # ! incompatible horizontal crs
    # crs_from, crs_to = "EPSG:32618+NOAA:5503", "EPSG:32618+EPSG:5703"


    # ! DE / VA / MD  >>  EPSG:9000(+NOAA:5200) >>> EPSG:6318(+NOAA:5200)
    crs_from, crs_to = "EPSG:6347", "EPSG:6347+NOAA:5200"
    # EPSG:6347 >>> EPSG:6319                           [NAD83(2011) (geographic 3D)]
    # EPSG:6319 >>> EPSG:7912                           [ITRF2014 (geographic 3D)]
    # EPSG:7912 >>> EPSG:9000+NOAA:5543                 [ITRF2014 + MSL (XGEOID20B_CONUSPAC) height]
    # EPSG:9000+NOAA:5543 >>> EPSG:9000+NOAA:5197       [ITRF2014 + LMSL height]
    # EPSG:9000+NOAA:5197 >>> EPSG:9000+NOAA:5200       [ITRF2014 + MLLW height]
    # EPSG:9000(+NOAA:5200) >>> EPSG:6318(+NOAA:5200)       [NAD83(2011) + MLLW height]
    # EPSG:6318+NOAA:5200 >>> EPSG:6347+NOAA:5200       [NAD83(2011) / UTM 18N + MLLW height]
    # linear: ['EPSG:6347', 'EPSG:6319', 'EPSG:7912', 'EPSG:9000+NOAA:5200', 'EPSG:6318+NOAA:5200', 'EPSG:6347+NOAA:5200']
    # graph without _compatiple: ['EPSG:6347', 'EPSG:6319', 'EPSG:4269', 'EPSG:6318+NOAA:5200', 'EPSG:6347+NOAA:5200']

    pipe = Pipeline(crs_from=crs_from,
                    crs_to=crs_to
                    )
    linear_route, graph_route, graph_k_routes= [], [], []
    try:
        linear_route = pipe.linear_steps()
    except Exception as e:
        print(str(e))   
    try:
        graph_route = pipe.graph_steps()
    except Exception as e:
        print(str(e))
    try:
        graph_k_routes = pipe.k_graph_steps(k=20)
    except Exception as e:
        print(str(e))  

    print(f"\n\n{'-'*20} Routes {'-'*20}")
    print(f"Linear Algorithm: {linear_route}")
    print(f"Graph Algorithm: {graph_route}")
    # print(f"Graph k-Route: {graph_k_routes}")
