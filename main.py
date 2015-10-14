
import gevent.monkey
gevent.monkey.patch_all()

import json
import logging

import gevent
import gevent.pool

import argh

from common import open_sheet, get_rows, update_column
from cutting import process

MAX_JOBS = 8


with open('config.json') as f:
	CONFIG = json.load(f)


def get_rows_to_do(sheet, restart_in_progress=False, restart_errors=False):
	"""Return all rows that are ready to be cut. If restart_in_progress, also include rows listed
	as already being cut (this is useful for recovery if they were interrupted).
	If restart_errors, re-attempt any jobs that errored."""
	logging.info("Checking for new jobs")
	for row in get_rows(sheet):
		if row['Ready for VST'] != 'Ready':
			continue
		state = row['Processed by VST']
		if state == 'Not Yet':
			yield row
		elif restart_in_progress and state == 'In Progress':
			yield row
		elif restart_errors and state == 'Errored':
			yield row


def start_jobs(jobs, sheet, **kwargs):
	"""Find any new jobs to do and start them in the background"""
	for row in get_rows_to_do(sheet, **kwargs):
		logging.debug("Trying to start job {}".format(row['id']))
		jobs.wait_available()
		update_column(sheet, row['id'], 'Processed by VST', 'In Progress')
		jobs.spawn(process, sheet, row)
		logging.debug("Started job {}".format(row['id']))


def main(interval=10, restart_in_progress=False, restart_errors=False, log_level='DEBUG'):
	logging.basicConfig(level=log_level)
	jobs = gevent.pool.Pool(MAX_JOBS)
	sheet = open_sheet(CONFIG['sheet_id'], CONFIG['creds'])
	try:
		while True:
			start_jobs(jobs, sheet, restart_in_progress=restart_in_progress, restart_errors=restart_errors)
			restart_in_progress = False # restart in progress on first pass only (if at all)
			gevent.sleep(interval)
	except KeyboardInterrupt:
		logging.warning("Interrupt recieved. Waiting for {} jobs".format(len(jobs.greenlets)))
		jobs.kill(block=True)


if __name__ == '__main__':
	argh.dispatch_command(main)
