class BaseAction():
    name = ""
    __version__ = "0.0.1"
    @classmethod
    def get_name(cls):
        return cls.name
    @classmethod
    def get_version(cls):
        return cls.__version__
