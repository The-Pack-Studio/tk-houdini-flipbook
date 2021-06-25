import os
import json

class JsonManager():
    def __init__(self, app, output_template, name):
        # retrieve root path
        fields = { 
            "name": name,
            "SEQ": "FORMAT: $F"
            }

        fields.update(app.context.as_template_fields(output_template))
        root_path = output_template.parent.parent.apply_fields(fields)

        self._json_path = os.path.join(root_path, '{}_data.json'.format(name))
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
        dirdir = os.path.dirname(self._json_path)
        if not os.path.exists(dirdir):
            os.makedirs(dirdir)

        self._write_json()

    def _write_json(self):
        with open(self._json_path, 'w') as json_data:
            json.dump(self._data, json_data, indent=4)

