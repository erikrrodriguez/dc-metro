import time
import gc
import displayio
from adafruit_display_shapes.rect import Rect
from adafruit_display_text.label import Label
from adafruit_matrixportal.matrix import Matrix

from config import config


class TrainBoard:
    """
    get_new_data is a function that is expected to return a dictionary of arrays of dictionaries like this:

    {
        'trains': [
            {
                'line_color': 0xFFFFFF,
                'destination': 'Dest Str',
                'text_arrival': '5'
                'int_arrival': 5
            },
        ],
        'buses': [
            {
                'line_color': 0x000000,
                'destination': 'C51 - N',
                'text_arrival': '5'
                'int_arrival': 5
            },
        ],
        'incidents': [
            {
                "description": "Red Line: Expect residual delays to Glenmont due to an earlier signal problem outside Forest Glen.",
            },
        ]
    }
    """

    def __init__(self, get_new_data):
        self.get_new_data = get_new_data
        self.display = Matrix().display
        self.parent_group = displayio.Group(scale=1, x=0, y=3)

        self.heading_label = Label(config["font"], anchor_point=(0, 0))
        self.heading_label.color = config["heading_color"]
        self.heading_label.text = config["heading_text"]
        self.parent_group.append(self.heading_label)

        self.lines = []
        for i in range(config["num_lines"]):
            self.lines.append(Line(self.parent_group, i))

        self.display.root_group = self.parent_group

    def refresh(self) -> bool:
        data = self.get_new_data()
        trains = data["trains"]
        buses = data["buses"]
        incidents = data["incidents"]

        if len(trains) > 0 or len(buses) > 0:
            trains_and_buses = trains + buses
        else:
            trains_and_buses = None

        if trains_and_buses is not None:
            for i in range(config["num_lines"]):
                if i < len(trains_and_buses):
                    line = trains_and_buses[i]
                    self._update_line(
                        i, line["line_color"], line["destination"], line["text_arrival"]
                    )
                else:
                    self._hide_line(i)
        else:
            print("No data received. Clearing display.")
            for i in range(config["num_lines"]):
                self._hide_line(i)

        if len(incidents) > 0:
            self._show_incidents(incidents)
        self.heading_label.text = config["heading_text"]
        print("Successfully updated.")

    def _show_incidents(self, incidents):
        for incident in incidents:
            self.heading_label.text = incident["description"]
            self._scroll(self.heading_label)

    def _scroll(self, label):
        label_width = label.bounding_box[2]
        while label.x > -label_width:
            label.x = label.x - 1
            time.sleep(config["scroll_delay"])
        label.x = 0

    def _hide_line(self, index: int):
        self.lines[index].hide()

    def _update_line(self, index: int, line_color: int, destination: str, minutes: str):
        self.lines[index].update(line_color, destination, minutes)

    def turn_off_display(self):
        self.display.brightness = 0

    def turn_on_display(self):
        self.display.brightness = 1


class Line:
    def __init__(self, parent_group, index):
        y = (int)(config["character_height"] + config["text_padding"]) * (index + 1)

        self.line_rect = Rect(
            0,
            y - 3,
            config["line_width"],
            config["line_height"],
            fill=config["loading_line_color"],
        )

        self.info_label = Label(config["font"], anchor_point=(0, 0))
        self.info_label.x = config["line_width"] + 1
        self.info_label.y = y
        self.info_label.color = config["text_color"]
        self.info_label.text = (
            config["loading_destination_text"] + "  " + config["loading_min_text"]
        )

        # self.destination_label = Label(config["font"], anchor_point=(0, 0))
        # self.destination_label.x = config["line_width"] + 1
        # self.destination_label.y = y
        # self.destination_label.color = config["text_color"]
        # self.destination_label.text = config["loading_destination_text"]

        # self.min_label = Label(config["font"], anchor_point=(0, 0))
        # self.min_label.x = (
        #     config["matrix_width"]
        #     - (config["min_label_characters"] * config["character_width"])
        #     + 1
        # )
        # self.min_label.y = y
        # self.min_label.color = config["text_color"]
        # self.min_label.text = config["loading_min_text"]

        self.group = displayio.Group(scale=1, x=0, y=0)
        self.group.append(self.line_rect)
        # self.group.append(self.destination_label)
        # self.group.append(self.min_label)
        self.group.append(self.info_label)

        parent_group.append(self.group)

    def show(self):
        self.group.hidden = False

    def hide(self):
        self.group.hidden = True

    def set_line_color(self, line_color: int):
        self.line_rect.fill = line_color

    def set_destination(self, destination: str):
        self.destination_label.text = destination[
            : config["destination_max_characters"]
        ]

    def set_arrival_time(self, minutes: str):
        # Ensuring we have a string
        minutes = str(minutes)
        minutes_len = len(minutes)

        # Left-padding the minutes label
        minutes = " " * (config["min_label_characters"] - minutes_len) + minutes

        self.min_label.text = minutes

    def set_info_label(self, destination: str, minutes: str):
        dest_str = destination[: config["destination_max_characters"]]

        padding = " " * (
            int(config["destination_max_characters"])
            - len(destination)
            + (4 - len(minutes))
        )
        self.info_label.text = f"{dest_str}{padding}{minutes}"

    def update(self, line_color: int, destination: str, minutes: str):
        self.show()
        self.set_line_color(line_color)
        # self.set_destination(destination)
        # self.set_arrival_time(minutes)
        self.set_info_label(destination, minutes)


class ErrorBoard:
    def __init__(self, error_msg):
        self.display = Matrix().display
        self.display.brightness = 1
        self.parent_group = displayio.Group()

        self.label_1 = Label(
            config["font"], color=config["heading_color"], text=error_msg
        )
        self.label_1.anchor_point = (0, 0)
        self.label_1.anchored_position = (0, 12)
        text_width = self.label_1.bounding_box[2]

        # Create Label 2 for marquee scrolling
        self.label_2 = Label(
            config["font"], color=config["heading_color"], text=error_msg
        )
        self.label_2.anchor_point = (0, 0)
        spacing = 30  # Pixels between the end and the restart
        self.label_2.anchored_position = (text_width + spacing, 12)

        self.parent_group.append(self.label_1)
        self.parent_group.append(self.label_2)
        self.display.root_group = self.parent_group

        while True:
            self._scroll(text_width, spacing)

    def _scroll(self, text_width, padding):
        self.label_1.x -= 1
        self.label_2.x -= 1

        if self.label_1.x < -text_width:
            self.label_1.x = self.label_2.x + text_width + padding

        if self.label_2.x < -text_width:
            self.label_2.x = self.label_1.x + text_width + padding

        time.sleep(config["scroll_delay"])
