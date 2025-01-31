import os
import platform
import sqlite3
import logging
from typing import Optional, Tuple, Union
import pyproj as pp
from pathlib import Path
import pandas as pd
from vyperdatum.enums import PROJDB as enuPDB


logger = logging.getLogger("root_logger")


class DB:

    def __init__(self,
                 db_dir: Optional[str] = enuPDB.DIR.value
                 ) -> None:
        """

        Parameters
        ----------
        db_dir: str
            Path to the directory where the proj database file is located. The
            default values is pyproj data directory (`pyproj.datadir`).

        Returns
        -------
        NoneType
        """
        self.db_dir = db_dir
        self.db_name = enuPDB.FILE_NAME.value
        self.db_file_path = Path(self.db_dir).joinpath(self.db_name)

        if db_dir != pp.datadir.get_data_dir():
            self.update_db_path()
        return

    def __str__(self):
        return (f"db_dir: {self.db_dir}\ndb_file_path: {self.db_file_path}"
                "\nproj.datadir: {pp.datadir.get_data_dir()}"
                )

    def __repr__(self):
        return f"DB(data_dir = r'{self.db_dir}')"

    @property
    def db_file_path(self) -> str:
        return self._db_file_path

    @db_file_path.setter
    def db_file_path(self, db_path: str):
        if not db_path.is_file():
            raise FileNotFoundError(f"Proj Database file not found at: {db_path}")
        self.db_dir = os.path.dirname(db_path)
        self.db_name = os.path.basename(db_path)
        self._db_file_path = db_path

    def update_db_path(self) -> bool:
        """
        Prepend `self.db_dir` to `pyproj.datadir` which guides the pyproj
        to first look for the database at `self.db_dir` address.

        Raises
        -------
        ValueError:
            If `.db_dir` is not set.
        FileNotFoundError:
            If the database file is not found.


        Returns
        -------
        bool:
            `True` if the `data_dir` is set successfully, otherwise `False`.
        """
        try:
            success = False
            if not self.db_dir:
                raise ValueError("Attribute `.db_dir` not specified.")
            sep = ";" if platform.system() == "Windows" else ":"
            pp.datadir.set_data_dir(self.db_dir + sep + pp.datadir.get_data_dir())
            if pp.datadir.get_data_dir().split(sep)[0] != self.db_dir:
                raise SystemExit("Unable to set the path to the custom PROJ database.")
            else:
                success = True
        finally:
            return success

    def _connect(self) -> Tuple[Optional[object], Optional[object]]:
        """
        Connect to the proj database.

        Returns
        -----------
        obj:
            database connection object
        obj:
            database cursor object
        """
        try:
            con, cur = None, None
            con = sqlite3.connect(self.db_file_path)
            cur = con.cursor()
        except Exception:
            logger.exception(f"Error while connecting to database at {self.db_file_path}.")
        return con, cur

    def query(self,
              sql: str,
              dataframe: bool = False
              ) -> Union[Optional[list], Optional[pd.DataFrame]]:
        """
        Execute a sql query and return the response. This method is intended
        to run a read (scan) query.
        Avoid using this method for DML/DDL type operations.

        Parameters
        ----------
        sql: str
            SQL query (intended to be a scan query) to be executed.
        dataframe: bool, default=False
            If True, converts the result into a pandas dataframe.

        Returns
        --------
        list or pd.DataFrame
        """
        try:
            con, cur, res = None, None, None
            con, cur = self._connect()
            cur.execute(sql)
            res = cur.fetchall()
            # logger.info(res)
            if dataframe:
                res = pd.DataFrame.from_records(res,
                                                columns=[column[0] for column in cur.description]
                                                )
        except Exception:
            logger.exception("Error in db.query.")
        finally:
            if cur:
                cur.close()
            if con:
                con.close()
        return res

    def crs_by_keyword(self,
                       keywords: list[str],
                       dataframe: bool = False
                       ) -> Union[Optional[list], Optional[pd.DataFrame]]:
        """
        Return a list (or dataframe) of CRS that their name or description
        contain the passed keywords. The search is not case-sensitive.

        Parameters
        ----------
        sql: str
            SQL query (intended to be a scan query) to be executed.
        keywords: list[str]
            A list of string keywords used to query the database.
        dataframe: bool, default=False
            If True, converts the result into a pandas dataframe.

        Raises
        -------
        TypeError:
            If `keywords` is not a list of strings.
        ValueError:
            If no keywords is passed.

        Returns
        --------
        list or pd.DataFrame
        """
        if not isinstance(keywords, list):
            raise TypeError("keywords must be a list")
        if not all(map(lambda k: isinstance(k, str), keywords)):
            raise TypeError("keywords must be a list of strings")
        if len(keywords) < 1:
            raise ValueError("at least one keyword most be passed")
        where = ""
        filters = [f"(name like '%{k}%' OR description like '%{k}%')" for k in keywords]
        if len(filters) > 0:
            where = "WHERE " + " AND ".join(filters)
        return self.query(sql=f"SELECT * FROM {enuPDB.VIEW_CRS.value} {where}",
                          dataframe=dataframe)
