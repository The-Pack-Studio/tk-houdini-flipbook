import os
import json

class JsonManager():
    def __init__(self, root_path, name):
        self._json_path = os.path.join(root_path, 'flipbook_panel', '{}_data.json'.format(name))
        self._data = {}
        
        self._convert_existing_data(os.path.join(root_path, 'flipbook_panel'))
        
        if os.path.exists(self._json_path):
            with open(self._json_path, 'r') as json_data:
                self._data = json.load(json_data)

    def _convert_existing_data(self, flipbook_root):
        if not os.path.exists(self._json_path) and os.path.exists(flipbook_root):
            files = os.listdir(flipbook_root)
            comments = []

            for name in files:
                if name.split('.')[-1] == 'txt':
                    comments.append(name)

            for comment in comments:
                text_file = open(os.path.join(flipbook_root, comment), "r")
                text = text_file.read()
                self._data[comment.split('.')[0]] = {'comment': text}

                text_file.close()

            with open(self._json_path, 'w') as json_data:
                json.dump(self._data, json_data, indent=4)

    def get_item_data(self, item_name):
        if item_name in self._data.keys():
            return self._data[item_name]
        return {}

    def remove_item(self, item_name):
        if item_name in self._data.keys():
            self._data.pop(item_name)

            with open(self._json_path, 'w') as json_data:
                json.dump(self._data, json_data, indent=4)

    def write_item_data(self, item_name, item_data):
        self._data[item_name] = item_data

        # create dir if it doesn't exist
        if not os.path.exists(self._json_path):
            os.makedirs(os.path.dirname(self._json_path))

        with open(self._json_path, 'w') as json_data:
            json.dump(self._data, json_data, indent=4)

