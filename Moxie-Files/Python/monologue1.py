# README: Creates property data that gets passed to "monologue.jinja"

import csv
import os

from ....... import CHATSCRIPT_ROOT
from .....logs import log
from ...flexible.flexible_node_data import FlexibleNodeData


class FlexibleMonologue1(FlexibleNodeData):
    _CONTINUE_MONOLOGUE_PROPS = FlexibleNodeData.new_text_and_markup_properties(
        text_jinja_name="continue_monologue_text",
        markup_jinja_name="markup_continue_monologue_text",
        text_prop_name="continueMonologueText",
        displayed_name="Continue Monologue Text",
        hint="text that plays immediately after continuing the monologue"
    )
    _CONTINUE_MONOLOGUE_PROPS.extend(
        FlexibleNodeData.new_pattern_properties(
            displayed_name="Continue Monologue Pattern",
            hint="Pattern that user needs to match to continue the monologue",
            pattern_jinja_name="continue_monologue_pattern",
            name="continueMonologuePattern"
        )
    )

    _FINISHED_MONOLOGUE_PROPS = FlexibleNodeData.new_move_on_properties(
        move_on_name="FinishedMonologue",
        jinja_name="finished_monologue_move_on_topic",
        displayed_name="Finished Monologue Move On Topic Name",
        hint="After finishing the monologue, move on to this node.",
        text_jinja_name="",
        pattern_jinja_name=""
    )

    _EARLY_EXIT_MONOLOGUE_PROPS = FlexibleNodeData.new_move_on_properties(
        move_on_name="EarlyExitMonologue",
        jinja_name="early_exit_monologue_move_on_topic",
        displayed_name="Early Exit Monologue Move On Topic Name",
        hint="Exit monologue early, move on to this node.",
        required=False,
        text_jinja_name="",
        pattern_jinja_name=""
    )
    _EARLY_EXIT_MONOLOGUE_PROPS.extend(
        FlexibleNodeData.new_pattern_properties(
            displayed_name="Early Exit Monologue Pattern",
            hint="Pattern that user needs to match to exit the monologue early",
            pattern_jinja_name="early_exit_monologue_pattern",
            name="earlyExitMonologuePattern",
            required=False
        )
    )

    _LOST_TARGET_CONFIRMATION_MONOLOGUE_PROPS = FlexibleNodeData.new_text_and_markup_properties(
        text_jinja_name="lost_target_confirmation_monologue_text",
        markup_jinja_name="markup_lost_target_confirmation_monologue_text",
        text_prop_name="lostTargetConfirmationMonologueText",
        displayed_name="Lost Target Confirmation Monologue Text",
        hint="text that plays after receiving eb-lost-target with confirmation option on"
    )

    _MONOLOGUE_SHEET = FlexibleNodeData.new_csv_properties(
        displayed_name="CSV File Path",
        hint="the csv file path containing the desired monologue lines"
    )

    _MONOLOGUE_TIMER_PROPS = FlexibleNodeData.new_fixed_choice_properties(
        fixed_choice_jinja_name='monologue_timer_value',
        fixed_choice_prop_name="monologueTimerValue",
        displayed_name="Monologue timer value",
        hint="time in seconds before the next monologue line",
        required=False,
        defaultValue="monologue(0.25s)",
        possibleValues=["monologue(0.25s)","short(1.0s)","medium(3.0s)","long(5.0s)","reprompt(10.0s)"]
    )

    _FALLBACK_OUTPUT_PROPS = FlexibleNodeData.new_fixed_choice_properties(
        fixed_choice_jinja_name="fallback_monologue_choice",
        fixed_choice_prop_name="fallbackOutputMonologueChoice",
        displayed_name="Falllback Output Monologue Choice",
        hint="What moxie does when the user says a fallback during a monologue node.",
        required=False,
        defaultValue="moxieInterested",
        possibleValues=["moxieInterested","eyesClosed"]
    )

    def __init__(self):
        super().__init__()
        self.name = "monologue_v1"
        self.displayedName = "Interactions/Monologue"
        self.templateName = "Monologue.jinja"
        self.outgoingConnectionIDs = []
        # add unique props
        self.propertyDefinitions.extend(self._CONTINUE_MONOLOGUE_PROPS)
        self.propertyDefinitions.extend(self._FINISHED_MONOLOGUE_PROPS)
        self.propertyDefinitions.extend(self._EARLY_EXIT_MONOLOGUE_PROPS)
        self.propertyDefinitions.extend(self._LOST_TARGET_CONFIRMATION_MONOLOGUE_PROPS)
        self.propertyDefinitions.extend(self._MONOLOGUE_SHEET)
        self.propertyDefinitions.extend(self._MONOLOGUE_TIMER_PROPS)
        self.propertyDefinitions.extend(self._FALLBACK_OUTPUT_PROPS)
        self.new_fallback_context_properties(defaultValue="LOCAL_ONLY", possibleValues=["LOCAL_ONLY"], noContext=True)

    def update_prop_dict(self, prop_dict, **kwargs) -> dict:
        for prop_def in self.propertyDefinitions:
            if prop_def.type == FlexibleNodeData.Property.PropertyType.CSV_RELATIVE_PATH:
                # If we don't have a csv file, throw an error
                if not prop_def.jinjaName in prop_dict:
                    raise Exception(f"The Monologue node gently urges you to place a sheet in it -- {log.context(self.parent_element)}")

                else:
                    # Go through the csv file + needs the full filepath . . .
                    csv_full_path = os.path.join(CHATSCRIPT_ROOT, "chatscript", prop_dict[prop_def.jinjaName])
                    with open(csv_full_path, "r") as f:
                        csv_tags = f.readline()
                        csv_column_names = f.readline().strip().split(",")

                    # . . . and ensure that the csv file has a column titled "Markup"
                    hasMarkup = False

                    for col in csv_column_names:
                        if col == "Markup":
                            hasMarkup = True
                            break

                    if not hasMarkup:
                        raise Exception(f"Please have a column titled 'Markup' in your Monologue Node's csv! -- {log.context(self.parent_element)}")

        return prop_dict


    @staticmethod
    def get_description() -> str:
        return """Given a csv sheet full of dialogue lines, this node
        will play through each one from top to bottom with small pauses in between.
        
        This node contains a continue monologue pattern and speech output as well as an
        optional early monologue exit pattern and move on topic.

        The optional key/value properties, if provided, provides a filter on the input CSV, 
        allowing multiple monologues be represented within the same CSV file.
        """