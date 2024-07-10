class Risk(Chariot):
    def __init__(self, keychain, key, risk_data=None):
        super().__init__(keychain)
        self.key = key
        self.data = risk_data or {
            "name": "",
            "type": "",
            "severity": "",
            "status": "",
            "created": "",
            "description": ""
        }
        if risk_data:
            print(f"Risk {key} initialized with data: {risk_data}")
        else:
            print(f"Risk {key} initialized with no data.")

    def add_risk(self, risk_data):
        """
        Adds data to the risk.

        :param risk_data: Dictionary containing risk data
        """
        self.data.update(risk_data)
        print(f"Risk {self.key} added with data: {self.data}")

    def update_risk(self, risk_data):
        """
        Updates the risk data.

        :param risk_data: Dictionary containing updated risk data
        """
        self.data.update(risk_data)
        print(f"Risk {self.key} updated with data: {self.data}")

    def delete_risk(self):
        """
        Deletes the risk data.
        """
        self.data = None
        print(f"Risk {self.key} deleted.")

    def get_risk(self):
        """
        Retrieves the risk data.

        :return: Dictionary containing risk data
        """
        return self.data

    def __getattr__(self, item):
        """
        Custom attribute access to get data properties directly.
        """
        if item in self.data:
            return self.data[item]
        raise AttributeError(f"'Risk' object has no attribute '{item}'")
