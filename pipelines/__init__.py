"""This contains the Python files responsible for parsing and inserting data.

/analyses: The Python files responsible for parsing, sending data, and multiprocessing.

/management/commands: Wraps files from /analyses as Django commands for easier execution.

General order (if running from scratch after running migrations) goes like this:

python manage.py generate_organelle_records
python manage.py metadata_generator
python manage.py ir_setup
python manage.py ir_confirmation
python manage.py genome_upload

To fill pre-existing information just use:

python manage.py backfill_table_columns



"""
