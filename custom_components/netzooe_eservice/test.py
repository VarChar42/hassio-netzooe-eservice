import os
from eservice_api import EServiceApi

user = os.getenv('ESERVICE_USER')
pw = os.getenv('ESERVICE_PW')

api = EServiceApi(user, pw)

api.update()
print(api.state)