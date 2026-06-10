from abc import ABC, abstractmethod


class Driver(ABC):

    @abstractmethod
    def transform():
        ...

    @property
    @abstractmethod
    def is_valid():
        ...
