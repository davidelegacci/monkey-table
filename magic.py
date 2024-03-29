import pandas as pd
import os
import time
from datetime import datetime, timedelta
import numpy as np
import xarray as xr
from tqdm import tqdm
import sys
import logging
import shutil

from program_parameters import *
from myutils import *


####################################################################################################################################################################################
## START METADATA
####################################################################################################################################################################################

current_date = datetime.utcfromtimestamp( int(time.time()) ).strftime('%Y-%m-%d-%H_%M_%S')
initial_day_of_study = datetime(2021, 11, 2)


#pd.set_option("display.max_rows", None, "display.max_columns", None)

nan_value = float("NaN")
horizontal_line = '=' * os.get_terminal_size().columns
horizontal_line_before_space = f'\n{horizontal_line}'
horizontal_line_after_space = f'{horizontal_line}\n'

log = logging.getLogger(__name__)

####################################################################################################################################################################################
# END METADATA
####################################################################################################################################################################################


####################################################################################################################################################################################
## START ARGPARSE
####################################################################################################################################################################################

verbose = False
if '-v' in sys.argv:
	verbose = True

if verbose:
	def verprint(data):
		print(data)
else:
	def verprint(data):
		pass

# if debug is true, the program runs only on the files where it encoutered errors during the previous run
debug = False if '-debug' not in sys.argv else True

####################################################################################################################################################################################
## END ARGPARSE
####################################################################################################################################################################################


####################################################################################################################################################################################
# START PATIENTS MAP 8-digit!
####################################################################################################################################################################################
patients_map = pd.read_excel(patients_map_path, keep_default_na = False)
patients_map['DAY0'] = pd.to_datetime(patients_map['DAY0'], dayfirst = True)

# this function returns 8-digit identifier
#def patNum2ID(num):
#	return patients_map[ patients_map.LFDNR == num ].PATIFALLNR.iloc[0]

# this function takes 8-digit identifier
def patID2Num(ID):
	return patients_map[ patients_map.PATIFALLNR == ID ].LFDNR.iloc[0]


####################################################################################################################################################################################
# END PATIENTS MAP
####################################################################################################################################################################################



####################################################################################################################################################################################
# START DATA MERGING ROUTINE
# Goal: from multiple csv, each with data of multiple patients, get multiple excel files, each with all the data of a single patient
####################################################################################################################################################################################
perform_merging_routine = ''

if not debug: 
	while perform_merging_routine not in ['y', 'n']:
		perform_merging_routine = input("\nPerform merging routine? Type y or n: ")

if perform_merging_routine == 'y':

	lab_results_directory = f'{directory_merged_results_per_patient}/{current_date}'   # one file per patient
	lab_results_directory_debug = f'{directory_merged_results_per_patient_debug}/{current_date}'   # one file per patient

	def save_excel_patient_sheet(df, dirname, filename):

		filepath = f'{dirname}/{filename}'
		os.makedirs(dirname, exist_ok=True)

		with pd.ExcelWriter(filepath) as writer:
			df.to_excel(writer, index = False)

	raw_data = []
	for raw_result in os.listdir(lab_results_raw_directory):
		if raw_result.endswith(".csv") and not raw_result.startswith("~"):
			print(f'\n Extracting data from {raw_result}...')
			# encoding https://stackoverflow.com/questions/42339876/error-unicodedecodeerror-utf-8-codec-cant-decode-byte-0xff-in-position-0-in
			# separator https://stackoverflow.com/questions/18039057/python-pandas-error-tokenizing-data
			current_df = pd.read_csv(f'{lab_results_raw_directory}/{raw_result}', encoding='cp1252', sep = ';')
			# replace empty with NaN, and kill Nan
			current_df.replace("", nan_value, inplace=True)
			current_df.dropna(inplace=True)
			raw_data.append( current_df )  

	# Merge into single
	raw_df = pd.concat( raw_data )
	raw_df = raw_df.astype({"PATIFALLNR": int})

	print('\n All raw results merged into single result!')


	# 9-digit
	patient_IDs_in_current_labresults = set(raw_df.PATIFALLNR)
	patient_IDs_in_current_labresults_8_digit = set([p//10 for p in raw_df.PATIFALLNR])
	#print(patient_IDs_in_current_labresults)

	# 8-digit
	patient_IDs_in_patients_map = set(patients_map.PATIFALLNR)
	#print(patient_IDs_in_patients_map)
	#patients_in_current_labresults_not_in_map = patient_IDs_in_current_labresults - patient_IDs_in_patients_map

	# 9-digit
	patients_in_current_labresults_not_in_map = [p for p in patient_IDs_in_current_labresults if p//10 not in patient_IDs_in_patients_map]
	if len(patients_in_current_labresults_not_in_map) > 0:
		print(f'\n{horizontal_line}')
		print('These patients (8-digit PATIFALLNR) have labresults but are NOT in patients map, so the results about them are ignored.\n')
		[print(p//10) for p in patients_in_current_labresults_not_in_map ]
		print(horizontal_line)
		print()

	# 9-digit
	patients_in_map_but_number_missing = [ p for p in patient_IDs_in_patients_map if patID2Num(p) == '']
	if len(patients_in_map_but_number_missing) > 0:
		[print(p) for p in patients_in_map_but_number_missing ]
		print()
		raise Exception('\nThese PATIFALLNR patients have labresults and ARE in patients map, but they are not associated to a number. Fix the patients map. \n')

	print('\n Generating lab results file for each patient in patients map and in current result sheet...\n')

	patients_in_current_labresults_and_in_map_8_digit = patient_IDs_in_current_labresults_8_digit.intersection(patient_IDs_in_patients_map)

	# patient is 8-digit identifier
	for patient in tqdm(patients_in_current_labresults_and_in_map_8_digit):

		# patient_number is rebecca identifer
		patient_number = patID2Num(patient)
		
		raw_df_patient = raw_df[raw_df.PATIFALLNR//10 == patient]

		filename = f'{patient_number}-{patient}.xlsx'
		save_excel_patient_sheet(raw_df_patient, lab_results_directory, filename)

	print(f'\n{horizontal_line}')
	print('MERGING ROUTINE COMPLETED :)\n Starting data manipulation.')
	print(horizontal_line)

if perform_merging_routine == 'n':

	name_of_directory_with_most_recent_results = [directory for directory in sorted(os.listdir(directory_merged_results_per_patient), key=natsort) if not directory.startswith('.')][-1]

	lab_results_directory = f'{directory_merged_results_per_patient}/{name_of_directory_with_most_recent_results}'   # one file per patient

if debug:
	name_of_directory_with_most_recent_results_debug = [directory for directory in sorted(os.listdir(directory_merged_results_per_patient_debug), key=natsort) if not directory.startswith('.')][-1]

	lab_results_directory = f'{directory_merged_results_per_patient_debug}/{name_of_directory_with_most_recent_results_debug}'   # one file per patient

	print(red('\nDEBUG MODE ON\n'))

####################################################################################################################################################################################
# END DATA MERGING ROUTINE
####################################################################################################################################################################################




####################################################################################################################################################################################
# START DATA MANIPULATION ROUTINE FOR EACH PATIENT
####################################################################################################################################################################################



def period_maker():
	'''Returns [7, 7, 7, 2] if num_max_days = 23 and sub_period_duration = 7'''
	if num_max_days < sub_period_duration:
		raise Exception('First input must be >= second')
	if num_max_days % sub_period_duration == 0:
		raise Exception(f'\n\nFor technical reasons num_max_days {num_max_days} cannot be a multiple of sub_period_duration {sub_period_duration}. To resolve set for example num_max_days to {num_max_days+1}.\n ')
	num_full_sub_periods = int(num_max_days/sub_period_duration)
	days_in_final_subperiod = num_max_days % sub_period_duration
	period_list = [sub_period_duration for _ in range(num_full_sub_periods)]
	if days_in_final_subperiod != 0: period_list = period_list +[days_in_final_subperiod]
	return period_list

def data_splitter(data):
	'''Given data of lenght num_max_days splits it according to period_maker

	e.g. num_max_days = 11
	sub_period_duration = 3
	period_list = period_maker() returns [3, 3, 3, 2]
	data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

	data_splitter(data) returns [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11]]

	'''
	period_list = period_maker()
	helper = [sum(period_list[:i]) for i in range(len(period_list)+1)]
	return [  data[helper[i]:helper[i+1]] for i in range(len(helper)-1) ]

all_days = [_ for _ in range(num_max_days)]
split_days = data_splitter(all_days)
#print(split_days)


def dictionary_values_splitter(dictionary_to_split):
	return { k:data_splitter(v) for k,v in dictionary_to_split.items() }

def dict_of_lists_to_list_of_dicts(dict_of_lists):
	return [ dict(zip(dict_of_lists, i)) for i in zip(*dict_of_lists.values()) ]


# START FIXING PARAMETERS NAMES
# Real parameters are read from parameters.txt
all_needed_parameters = generate_parameters('parameters_directory/parameters.txt')
all_needed_parameters_before_fixing_names = all_needed_parameters[:]
verprint(f'\nHere are all needed parameters before fixing names: \n\n {all_needed_parameters}\n\n')

parameters_strange_characters_from_lab = generate_parameters('parameters_directory/parameters_strange_characters_from_lab.txt')
parameters_strange_characters_from_lab_python = generate_parameters('parameters_directory/parameters_strange_characters_from_lab_python.txt')

parameters_strange_characters_from_lab_corrected = generate_parameters('parameters_directory/parameters_strange_characters_from_lab_corrected.txt')

parameters_correction_dictionary = dict_from_two_lists(parameters_strange_characters_from_lab, parameters_strange_characters_from_lab_corrected)
parameters_correction_dictionary_python = dict_from_two_lists(parameters_strange_characters_from_lab_python, parameters_strange_characters_from_lab_corrected)

# Acts in place; remove parameters with strange names from all needed parameters with those with correct names
# The same procedure has to be done on the data, using parameters_correction_dictionary_python
replace_list_elements_by_dict(all_needed_parameters, parameters_correction_dictionary)
verprint('\nHere are all needed parameters before and after fixing names:\n')
for i in range(len(all_needed_parameters_before_fixing_names)):
	#if all_needed_parameters_before_fixing_names[i] in parameters_strange_characters_from_lab:
	if all_needed_parameters_before_fixing_names[i] != all_needed_parameters[i]:
		verprint(orange(f'{all_needed_parameters_before_fixing_names[i]} /// {all_needed_parameters[i]}'))
	else:
		verprint(f'{all_needed_parameters_before_fixing_names[i]} /// {all_needed_parameters[i]}')

# END FIXING PARAMETERS NAMES


#num_patients = 0
patient_identifier_PATIFALLNR = []
day0_all_patients = []

# Multiple sheets

number_of_sheets = int(num_max_days/sub_period_duration) + 1

big_data_multiple_sheets = [  [ ] for _ in range(number_of_sheets)  ]



# START PATIENT
patients_with_error = []
# Read each excel file in lab_results_directory into dataframe and put it into data_list
print('\n Starting patients loop...')
for patient in tqdm( sorted(os.listdir(lab_results_directory), key=natsort) ):
	# make sure to select only excel files; sometimes hidden files like ~$patient.xlsx are created, which must be excluded:
	if patient.endswith(".xlsx") and not patient.startswith("~"):

		try:
			#num_patients +=1
			verprint(f'\n{horizontal_line}')
			verprint(horizontal_line)
			verprint(orange(f'--> Processing patient {patient}...\n'))

			# START MERGING DATAFRAME
			# Read data into two df
			data = pd.read_excel(f'{lab_results_directory}/{patient}') #, skiprows = 2, usecols = 'A, B, C, D')

			# Get rid of spaces in columns
			#data.columns = data.columns.str.replace(' ', '')

			# Get rid of » symbol in indiced
			# data.BESCHREIBUNG = data.BESCHREIBUNG.str.replace(' »', '')

			# drop not needed columns
			#not_needed_columns = ['AUFTRAGNR', 'GEBDAT', 'SEX', 'EINSCODE', 'LABEINDAT']
			needed_columns = ['PATIFALLNR', 'BESCHREIBUNG', 'ERGEBNIST', 'LABEINDAT']
			for col in data.columns:
				if col not in needed_columns:
					data.drop(col, axis = 1, inplace = True)

			# Replace weird german characters parameters names with normal ones

			verprint(horizontal_line_before_space)
			verprint(f'Here is the data before renaming weird parameters: \n \n {data}')

			for i in range(len(data.BESCHREIBUNG)):
				if data.at[i, 'BESCHREIBUNG'] in parameters_strange_characters_from_lab_python:
					data.at[i, 'BESCHREIBUNG'] = parameters_correction_dictionary_python[data.at[i, 'BESCHREIBUNG']]

			verprint(f'Here is the data after renaming weird parameters: \n \n {data}')
			verprint('Things are ok if the names in all needed and in data AFTER CORRECTION match.')
			verprint(horizontal_line_after_space)

			# IF INSTEAD PARAMETERS ARE VALUES OF COLUMN # <----------- MAIN DROP
			# https://stackoverflow.com/questions/18172851/deleting-dataframe-row-in-pandas-based-on-column-value

			# From labresults, drop parameters that are not needed
			for param in data.BESCHREIBUNG:
				if param not in all_needed_parameters:
					verprint(red(f'{param} is in lab results, but is not one of the needed parameters, so I am dropping it \n'))
					data.drop(data.index[ data.BESCHREIBUNG == param ], inplace = True) 

					# Should be allright without this
					# try:
					#   data.drop(data.index[ data.BESCHREIBUNG == param ], inplace = True)
					# except:
					#   pass

			# Since some rows were dropped, not index looks like [0, 1, 5, 9, 15, ...]
			# Which is a mess because data.colum[i] refers to that index. So need to reset.
			data.reset_index(inplace = True, drop = True)



			# Now not needed parameters are dropped from data.BESCHREIBUNG. It may still happen that a needed parameter is not present in result. Fixed later. 




			# Fix dates format
			# for i in range(len(data.LABEINDAT)):

			#   # Some dates were recognized by pandas already as datetimes; other are still strings because 1. they contain spaces and 2. they contain . rather than /
			#   if type( data.at[i, 'LABEINDAT'] ) is str:
			#       data.at[i, 'LABEINDAT'] = data.at[i, 'LABEINDAT'].replace(' ', '')
			#       data.at[i, 'LABEINDAT'] = data.at[i, 'LABEINDAT'].replace('.', '/')   

			# Convert to datetime
			data['LABEINDAT'] = pd.to_datetime(data['LABEINDAT'], dayfirst = True)

			# Add column only with info about day
			data = data.assign(DAY=data['LABEINDAT'].dt.strftime('%Y-%m-%d'))
			data['DAY'] = pd.to_datetime(data['DAY'], dayfirst = True)
			# This way DAY contains datetime objects, but keeps only year, month and date forgetting about hour, minute and second
			# ---------------------------------------------------------------------------------------------------

			#START GETTING RID OF kein material ROWS
			if keep_kein_material == 'n':
				strings_to_kill = ['Kein Material', 'K.Mat.']
				for s in strings_to_kill:
					index_to_kill = data.index[ data.ERGEBNIST == s ]
					[ print(f"---------------Dropping {s} for {data.at[ i , 'Parameter']}") for i in list(index_to_kill) ]
					data.drop(index_to_kill, inplace = True)

				data.reset_index(inplace = True, drop = True)

			# END GETTING RID OF kein material ROWS

			# NON STANDARD RESULTS
			# + and positive to 1
			# - and negative to empty
			# anything else remains text

			# Get rid of !L and !H flags
			for i in range(len(data.ERGEBNIST)):
				if type( data.at[i, 'ERGEBNIST'] ) is str:
					#data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace(' !L', '')
					#data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace(' !H', '')
					data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace('negativ', negative_result)
					data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace('-', negative_result)
					data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace('positiv', positive_result)
					data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace('+', positive_result)

					#This converts results to float if possible
					try:
						data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace(',', '.')
						data.at[i, 'ERGEBNIST'] = float(data.at[i, 'ERGEBNIST'])
					except:
						pass

			# END NON STANDARD RESULTS

			# START GETTING RID OF DUPLICATE EXAM 
			# POSSIBILITIES:
			
			# 1. Restructure all so that parameters are column, not index, and use
			# https://stackoverflow.com/questions/50885093/how-do-i-remove-rows-with-duplicate-values-of-columns-in-pandas-data-frame

			# 2. Keep parameters as index, work on sub-frames for each parameter, drop duplicate date column
			# Then reconstruct big dataframe by composition

			## IMPROVED DUPLICATED ALGORITH: KEEP WITH THIS PRIORITY
			# - the one done closest in time to penkid
			# - the first of the day

			# First make sure reference parameter does not appear more than once per day
			df_specific_for_reference_parameter = data.loc[ data.BESCHREIBUNG == reference_parameter ]
			boolean_duplicated_series_reference = df_specific_for_reference_parameter.duplicated( ['BESCHREIBUNG', 'DAY'], keep = False )
			if( boolean_duplicated_series_reference.any() ):
				df_duplicated_reference_parameter = df_specific_for_reference_parameter[boolean_duplicated_series_reference]
				
				for day in set(df_duplicated_reference_parameter.DAY):
					df_duplicated_reference_parameter_day = df_duplicated_reference_parameter[ df_duplicated_reference_parameter.DAY == day ]

					# print(df_duplicated_reference_parameter_day)
					# print()
					# print('---')
					# for p in df_duplicated_reference_parameter_day.ERGEBNIST:
					# 	print(p)
					# 	print(type(p))
					# print('---')

					# Keep earlies numerical result, or earliest result if no result is a number
					# https://stackoverflow.com/questions/50967231/pandas-select-rows-by-type-not-dtype
					try:
						index_to_keep_reference = df_duplicated_reference_parameter_day[df_duplicated_reference_parameter_day.ERGEBNIST.map(type)==float]['LABEINDAT'].idxmin()
					except:
						index_to_keep_reference = df_duplicated_reference_parameter_day['LABEINDAT'].idxmin()
					#print(index_to_keep_reference)
					#print()
					#print(df_duplicated_reference_parameter_day[index_to_keep_reference])
					#print()
					#print(df_duplicated_reference_parameter_day)
					for i in df_duplicated_reference_parameter_day.index:
						if str(i) != str(index_to_keep_reference):
							data.drop(i, inplace = True)
				data.reset_index(inplace = True, drop = True)
				#input(f'\n ---- ALERT----- \n\n Reference parameter {reference_parameter} appears more than once per day. Keeping first of each day. Enter to continue' )


			##############################################
			# Now deal with duplicates of all other parameters

			# OPTION 1
			#data.drop_duplicates( ['Parameter', 'LABEINDAT'], keep = 'first', inplace = True, ignore_index = True  )
			for p in set(data.BESCHREIBUNG):
				#print(f'PERFORMING PARAMETER {p} WHILE REFERENCE IS {reference_parameter}\n')
				df_specific_for_p = data.loc[ data.BESCHREIBUNG == p ]

				# https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.duplicated.html
				boolean_duplicated_series = df_specific_for_p.duplicated( ['BESCHREIBUNG', 'DAY'], keep = False )

				if( boolean_duplicated_series.any() ):
					df_duplicated_p = df_specific_for_p[boolean_duplicated_series]
					for day in set(df_duplicated_p.DAY):
						df_duplicated_p_day = df_duplicated_p[ df_duplicated_p.DAY == day ]
						#print()
						#print(df_duplicated_p_day)
					   

						# Not reference parameter
						current_day = list(df_duplicated_p_day.DAY)[0]
						#####
						reference_df = data[ data.BESCHREIBUNG == reference_parameter ]
						reference_df = reference_df[ reference_df.DAY == current_day ]
						#reference_time = list(reference_df.LABEINDAT)[0]
						# print()
						# print('debug------------------')
						# print(reference_df)
						# print()
						# print('debug------------------')
						# print()
						#####

						# IF THERE IS PENKID COMPARE WITH PENKID
						try:
							# reference_df = data[ data.BESCHREIBUNG == reference_parameter ]
							# reference_df = reference_df[ reference_df.DAY == current_day ]
							reference_time = list(reference_df.LABEINDAT)[0]

							# IF THERE IS NUMERICAL RESULT, TAKE NUMERICAL CLOSET TO PENKID
							try:
								closest_time = find_nearest( df_duplicated_p_day[df_duplicated_p_day.ERGEBNIST.map(type)==float].LABEINDAT, reference_time ) 

							# IF NO RESULT IS NUMERICAL, TAKE CLOSEST TO PENKID
							except:
								closest_time = find_nearest( df_duplicated_p_day.LABEINDAT, reference_time )

							index_to_keep = df_duplicated_p_day.index[df_duplicated_p_day['LABEINDAT'] == closest_time].tolist()[0]
							# print('Comparison done')
							# print(f'reference_time: {reference_time}')

						# IF THERE IS NO PENKID TAKE THE FIRST RESULT OF THE DAY
						except:

							# IF THERE IS NUMERICAL RESULT, TAKE FIRST NUMERICAL
							try:
								index_to_keep = df_duplicated_p_day[df_duplicated_p_day.ERGEBNIST.map(type)==float]['LABEINDAT'].idxmin()

							# IF THERE IS NO NUMERICAL RESULT, TAKE FIRST 
							except:
								index_to_keep = df_duplicated_p_day['LABEINDAT'].idxmin()
						#     print('Just kept first')
						# print(f'Index to keep: {index_to_keep}\n')

						# DROP DUPLICATES

						for i in df_duplicated_p_day.index:
							if str(i) != str(index_to_keep):
								data.drop(i, inplace = True)

			data.reset_index(inplace = True, drop = True)
			
			# Reconvert results to number like 3,4 rather than 3.4, so that excel is happy.. #-------------------------------------------------------------------------------------------
			# Alternative: in Excel use dot as float separator https://www.officetooltips.com/excel_2016/tips/change_the_decimal_point_to_a_comma_or_vice_versa.html
			for i in range(len(data.ERGEBNIST)):
				if type( data.at[i, 'ERGEBNIST'] ) is float:
					data.at[i, 'ERGEBNIST'] = str(data.at[i, 'ERGEBNIST'])
					data.at[i, 'ERGEBNIST'] = data.at[i, 'ERGEBNIST'].replace('.', ',')


			# END GETTING RID OF DUPLICATE EXAM # ----------

			# END MANIPULATING DATAFRAME


			# CAREFUL ACTUALLY DAY0 IS FROM EXTERNAL SOURCE, IT MAY BE THAT NO EXAM IS TAKEN ON DAY 0 <------------------------------------------------------------------------------------------------------------------- temporary
			# Get patient day0 = when she enters hospital

			# 9-digit identifier
			current_patient_PATIFALLNR = data['PATIFALLNR'][0]

			


			# SWITCH THIS ON ONCE REAL DATA FOR DAY 0 IS AVAILABLE; NOW SIMULATE
			#print('TAKING CORRECT DATE')
			day0 = patients_map[ patients_map.PATIFALLNR == current_patient_PATIFALLNR//10 ].DAY0.iloc[0] #.strftime('%Y-%m-%d')
			#print(day0)


			# simulate day0 as day before day of first exam; to switch off once real data for time0 is available
			#day0 = day_of_first_exam - timedelta(days = 1)

			day0_all_patients.append(day0)


			# GETTING RID OF EXAMS DONE BEFORE DAY 0 and before november second 2021 and sort data by date
			#print(day0)
			data = data[ data.DAY >= day0 ]
			data = data[ data.DAY >= initial_day_of_study ]
			data.sort_values('DAY', inplace = True)
			# END GETTING RID OF EXAMS DOBE BEFORE DAY 0

			
			try:
				day_of_first_exam = min(data.DAY)
			except:
				raise Exception(f"It could be that every exam is done after day0; check patient map for patient {patient} ")


			if day0 > day_of_first_exam:
				raise Exception(f'\nFor patient {patient} day 0 is {day0} but first exam is done on {day_of_first_exam}\n')

			if day0 < initial_day_of_study:
				raise Exception(f'\nFor patient {patient} day 0 is {day0} but initial day of study is {initial_day_of_study}\n')
			  

			# Get range of time in which exams are taken; not really used anywhere
			day_first_exam, day_last_exam = min(data.LABEINDAT), max(data.LABEINDAT)
			exam_period = day_last_exam - day_first_exam
			# print(exam_period)

			# Check time period
			if exam_period > pd.Timedelta(num_max_days, unit = 'd'):
				print(red(f'\n\n-----------SOMETHING WRONG---------\n\n Exam period lasts {exam_period}, longer than {num_max_days} days\n----------\n'))
				raise Exception

			# Set maximal period of staying in the hospital; equal for everybody
			period = pd.date_range(start=day0, periods=num_max_days)
			# print(period)

			# PARAMETERS TO KEEP 

			# parameters actually present in lab results
			# parameters_needed_and_available_from_lab = list(set(data.BESCHREIBUNG)) # this works but CHANGES ORDER

			# this contains the parameters that are needed AND available from the lab results, in the same order of all_needed_parameters
			parameters_needed_and_available_from_lab = [ p for p in all_needed_parameters if p in list(data.BESCHREIBUNG )]

			# parameters_needed_and_available_from_lab is equal to data.BESCHREIBUNG, without repetitions
			parameters_needed_but_not_available_from_lab = [p for p in all_needed_parameters if p not in list(data.BESCHREIBUNG)]

			# for parameter in data.BESCHREIBUNG:
			#   if parameter not in parameters_needed_and_available_from_lab:
			#       data.drop(parameter, axis = 0, inplace = True)


			# data.sort_values(by=['LABEINDAT'], inplace = True) 
			# print(f'\nSorted by date \n {data}\n')

			# Start building dictionary

			# This worked with parameter as index
			# def get_results(parameter):
			#   try:
			#       # if there is more than one result
			#       return list(data.loc[parameter].ERGEBNIST)
			#   except:
			#       # if there is only one result
			#       return [data.loc[parameter].ERGEBNIST]

			# def get_dates(parameter):
			#   try:
			#       # if there is more than one result
			#       return list(data.loc[parameter].LABEINDAT)
			#   except:
			#       # if there is only one result
			#       return [data.loc[parameter].LABEINDAT]

			def get_results(parameter):
				return list(data[data.BESCHREIBUNG == parameter].ERGEBNIST)

			def get_dates(parameter):
				return list(data[data.BESCHREIBUNG == parameter].DAY)


			final_dictionary = {}
			for p in all_needed_parameters:
				if p in parameters_needed_and_available_from_lab:
					final_dictionary[p] = [get_results(p), get_dates(p)]

				elif p in parameters_needed_but_not_available_from_lab:
					final_dictionary[p] = [ [empty_result for _ in range(num_max_days)] , 0 ]

				else:
					raise Exception('Something wrong')


			#print(final_dictionary)
			# Add empty in day when exam is not done
			for p in parameters_needed_and_available_from_lab:
				results, dates = final_dictionary[p]
				#print(dates)
				if len(results) < num_max_days:
					for i in range(num_max_days):
						if period[i] not in dates:
							#print(f'{period[i]} not in {dates}')
							results.insert(i,empty_result)

			# Collect all results; here final dictionary still contains dates, and [0] gets rid of it
			# patient_results = [ final_dictionary[p][0] for p in all_needed_parameters ]
			# big_data.append(patient_results)

			# Make dictionaries for multiple sheets
			final_dictionary_without_dates = { k:v[0] for k,v in final_dictionary.items() }

			# This list contains as many dictionaries as number of sheets, each to be treated as final_dictionary
			list_of_patient_dictionaries = dict_of_lists_to_list_of_dicts( dictionary_values_splitter( final_dictionary_without_dates ) )

			for s in range(number_of_sheets):
				big_data_multiple_sheets[s].append( list(list_of_patient_dictionaries[s].values()) )

			# each element of big_data_multiple_sheets is to be treated as big_data

			# contains 9-digit identifiers
			patient_identifier_PATIFALLNR.append(current_patient_PATIFALLNR)


			verprint(horizontal_line_before_space)
			verprint(f'\n Here is the final data for patient {patient}: \n\n {data} \n')

		except:
			print(horizontal_line)
			print(red(f'\n ------------>Error processing patient {patient}, so I skip it and continue with the others.\n To see the problem run the program again only on his/her file with the flag -debug.\n'))
			if debug:
				log.exception(orange(f'\nHere is what goes wrong with patient {patient}:\n'))
			patients_with_error.append(patient)
			print(horizontal_line)

if not debug:
	if len(patients_with_error) > 0:
		print(horizontal_line)
		print(red(f'Patients with errors: \n {patients_with_error}'))
		os.makedirs(lab_results_directory_debug, exist_ok=True)
		for file in patients_with_error:
		    shutil.copy(f'{lab_results_directory}/{file}', lab_results_directory_debug)

		print(horizontal_line)

####################################################################################################################################################################################
# END DATA MANIPULATION ROUTINE FOR EACH PATIENT
####################################################################################################################################################################################
print('\n Patient loop completed!')
####################################################################################################################################################################################
# START WRITING TO FINAL SHEET
####################################################################################################################################################################################
#print('\n Creating patient map, first step...')
patient_identifier_PATIFALLNR_last_digit_separated = [ f'{str(i)[:-1]}_{str(i)[-1:]}' for i in patient_identifier_PATIFALLNR  ]
#print('\n Creating patient map, second step...')
day0_all_patients_string = [d.strftime('%d-%m-%Y') for d in day0_all_patients]
patient_identifier_final = [ f'{patID2Num( patient_identifier_PATIFALLNR[i]//10 )} - {patient_identifier_PATIFALLNR_last_digit_separated[i]} - {day0_all_patients_string[i]}' for i in range(len(patient_identifier_PATIFALLNR_last_digit_separated)) ]

dims = ['patient', 'parameter', 'day']

def save_excel_sheet(df, dirname, filename, sheetname):

	filepath = f'{dirname}/{filename}'
	os.makedirs(dirname, exist_ok=True)

	if not os.path.exists(filepath):
		with pd.ExcelWriter(filepath) as writer:
			df.to_excel(writer, sheet_name=sheetname)
	else:
		with pd.ExcelWriter(filepath, engine='openpyxl', mode='a') as writer:
			df.to_excel(writer, sheet_name=sheetname)


print('\n Starting to write in Excel sheets...')
for s in tqdm(range(number_of_sheets)):
	#coords = {'patient':range(current_patient_one, current_patient_one+num_patients), 'parameter':all_needed_parameters, 'day':split_days[s] }
	coords = {'patient':patient_identifier_final, 'parameter':all_needed_parameters, 'day':split_days[s] }
	data = xr.DataArray(big_data_multiple_sheets[s], dims = dims, coords = coords )
	df = data.to_dataframe('value')
	df = data.to_series().unstack(level=[1,2])

	# filename = f'{current_patient_one}-{current_patient_one+num_patients-1}-{current_date}.xlsx'
	filename = f'{current_date}.xlsx'

	save_excel_sheet(df, directory_final_sheet, filename, f'Sheet{s+1}')

print(f'\n{horizontal_line}')
print('ALL GOOD :)')
print(f'{horizontal_line}')
if debug:
	print(orange('The debug went fine! Now implement the corrections you did in the debug lab sheet into the main lab sheet, and run the program without the -debug flag.'))





