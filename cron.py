import os

from crontab import CronTab


cron = CronTab(user=True)
cron.remove_all()
path = os.path.abspath("./coinmarketcapApi.py")
job = cron.new(command="cd " + os.path.abspath(".") + "; venv/bin/python " + "'" + path + "'")
job.minute.on(30)

cron.write()