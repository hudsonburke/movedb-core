"""
Sentinel objects for representing missing or unset values.
Inspiration from https://medium.com/the-pythonworld/never-use-none-for-missing-values-again-do-this-instead-8a92e20b6954
"""
#TODO

class Sentinel:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"<{self.name}>"


MISSING = Sentinel("MISSING")
MISSING_LIST = []
UNSET = Sentinel("UNSET")
