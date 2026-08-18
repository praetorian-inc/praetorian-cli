class Leaderboard:

    def __init__(self, api):
        self.api = api

    def get(self):
        return self.api.get('leaderboard')

    def get_weights(self):
        return self.api.get('leaderboard/weights')

    def set_weights(self, weights):
        return self.api.put('leaderboard/weights', weights)
