import os
import json

class JsonManager():
    def __init__(self, root_path, name):
        self._json_path = os.path.join(root_path, 'flipbook_panel', '{}_data.json'.format(name))
        self._data = {}
        
        if os.path.exists(self._json_path):
            with open(self._json_path, 'r') as json_data:
                self._data = json.load(json_data)

    def get_item_data(self, item_name):
        if item_name in self._data.keys():
            return self._data[item_name]
        return {}

    def remove_item(self, item_name):
        if item_name in self._data.keys():
            self._data.pop(item_name)

            self._write_json()

    def write_item_data(self, item_name, item_data):
        self._data[item_name] = item_data

        # create dir if it doesn't exist
        if not os.path.exists(self._json_path):
            os.makedirs(os.path.dirname(self._json_path))

        self._write_json()

    def _write_json(self):
        with open(self._json_path, 'w') as json_data:
            json.dump(self._data, json_data, indent=4)

