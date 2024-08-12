import json
import os

class Auth:
    def __init__(self):
        self.users_file = "users.json"
        self.current_user = None

        if not os.path.exists(self.users_file):
            with open(self.users_file, "w") as file:
                json.dump({}, file)

    def load_users(self):
        with open(self.users_file, "r") as file:
            return json.load(file)

    def save_users(self, users):
        with open(self.users_file, "w") as file:
            json.dump(users, file)

    def register(self, username, password):
        users = self.load_users()
        if username in users:
            return False
        users[username] = {"password": password}
        self.save_users(users)
        return True

    def login(self, username, password):
        users = self.load_users()
        if username in users and users[username]["password"] == password:
            self.current_user = username
            return True
        return False

    def change_password(self, username, current_password, new_password):
        users = self.load_users()
        if username in users and users[username]["password"] == current_password:
            users[username]["password"] = new_password
            self.save_users(users)
            return True
        return False