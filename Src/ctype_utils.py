from ctypes import Structure, BigEndianStructure, Array



def myprint(indent, s, *args, **kwargs):
    print(("  "*indent) + s, *args, **kwargs)


class PrintMixin:

    def show(self, indent = 0, print_name=True):
        if print_name:
            myprint(indent, f"{self.__class__.__name__}:")
        for field in self._fields_:
            name = field[0]
            value = getattr(self, name)

            if isinstance(value, PrintMixin):
                myprint(indent + 1, f"{name}:")
                value.show(indent + 2, print_name=False)
            elif isinstance(value, Array):
                if issubclass(value._type_, PrintMixin):
                    myprint(indent + 1, f"{name}:")
                    for index, item in enumerate(value):
                        myprint(indent + 2, f"{index}:")
                        item.show(indent + 3, print_name=False)
                else:
                    str_value = ", ".join(map(lambda x:str(x), value))
                    myprint(indent + 1, f"{name}: {str_value}")

            else:
                myprint(indent + 1, f"{name}: {value}")


class PrettyStructure(PrintMixin, Structure):
    pass

class PrettyBigEndianStructure(PrintMixin, BigEndianStructure):
    pass
