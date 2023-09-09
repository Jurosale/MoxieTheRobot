# README: Creates property data that gets passed to "SetRandomInt.jinja"

import copy
from .......logs import log
from ....flexible_node_data import FlexibleNodeData
from ..utilities import FlexibleUtilities

class FlexibleSetRandomInt1(FlexibleUtilities):

    _VARIABLE_NAME = FlexibleNodeData.Property(
        displayed_name="Variable Name",
        hint="The Name of this variable ($ not included)",
        jinja_name="var_name",
        name="varName",
        prop_type=FlexibleNodeData.Property.PropertyType.TEXT
    )

    def __init__(self):
        super().__init__()
        self.name = "set_random_int_v1"
        self.displayedName = "Logic/Variable/Set Random Integer Variable"
        self.templateName = "Logic/SetRandomInt.jinja"
        self.outgoingConnectionIDs = [
            "Continue"
        ]
        self.propertyDefinitions.append(self._VARIABLE_NAME)
        # use defined continue from FlexibleUtilities
        self.propertyDefinitions.extend(self._UTIL_CONTINUE)
        self.propertyDefinitions.extend([           
            self.Property(
                displayed_name="Min Integer Range (Inclusive)",
                hint="The lowest possible value that we can randomly assign",
                jinja_name="min_var_value",
                name="minVarValue",
                prop_type=self.Property.PropertyType.INTEGER
                ),

            self.Property(
                displayed_name="Max Integer Range (Inclusive)",
                hint="The highest possible value that we can randomly assign",
                jinja_name="max_var_value",
                name="maxVarValue",
                prop_type=self.Property.PropertyType.INTEGER
                )
        ])

    def update_prop_dict(self, prop_dict, **kwargs) -> dict:

        # Ensure the properties in this node are casted correctly
        min_value: Union[int, float]
        max_value: Union[int, float]
        min_name: str
        max_name: str
        type_required: str

        for prop_def in self.propertyDefinitions:
            if prop_def.type == FlexibleNodeData.Property.PropertyType.INTEGER or prop_def.type == FlexibleNodeData.Property.PropertyType.FLOAT:

                # If property was not set, throw an error about it
                if not prop_def.jinjaName in prop_dict:
                    raise Exception(f"A '{prop_def.displayedName}' field is currently empty. "
                                    f"Please check the last generated topic name above for more details on the error location "
                                    f"and fill in this value {log.context(self.parent_element)}.")

                # Else, type cast the value of the property
                # Throw out an error if we failed to cast it
                else:
                    try:
                        if prop_def.type == FlexibleNodeData.Property.PropertyType.INTEGER:
                            type_required = "integer"
                            casted_value = int(prop_dict[prop_def.jinjaName])
                        elif prop_def.type == FlexibleNodeData.Property.PropertyType.FLOAT:
                            type_required = "float number"
                            casted_value = float(prop_dict[prop_def.jinjaName])

                        if prop_def.jinjaName == "min_var_value":
                            min_value = casted_value
                            min_name = prop_def.displayedName
                        elif prop_def.jinjaName == "max_var_value":
                            max_value = casted_value
                            max_name = prop_def.displayedName

                    except ValueError as e:
                        raise Exception(f"The value inside a '{prop_def.displayedName}' field is not a(n) '{type_required}'. "
                                        f"Please check the last generated topic name above for more details on the error location "
                                        f"and correct this value:\n{e} {log.context(self.parent_element)}.")

                # Update the old property value with this new verified value
                prop_dict[prop_def.jinjaName] = casted_value

        # Ensure min value is less than or equal to the max value
        if min_value > max_value:
            raise Exception(f"A '{min_name}' field is greater than a '{max_name}' field. "
                            f"Please check the last generated topic name above for more details on the error location "
                            f"and correct these values {log.context(self.parent_element)}.")

        return prop_dict

    @staticmethod
    def get_description() -> str:
        return """
        given a minimum and maximum integer range (inclusive), grabs a random integer and assigns 

        it to the given variable name. This variable only persists while inside the current module.
        """