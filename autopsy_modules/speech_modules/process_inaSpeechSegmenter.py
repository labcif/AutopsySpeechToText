import csv
import functools

def processInaSpeechSegmenterCSV(path):
    with open(path) as csv_file:
        csv_reader = list(csv.reader(csv_file, delimiter='\t'))

    f = lambda x, line: x + float(line[2]) - float(line[1])

    male = filter(lambda line: line[0] == "Male", csv_reader)
    total_male = functools.reduce(f, male, 0)

    female = filter(lambda line: line[0] == "Female", csv_reader)
    total_female = functools.reduce(f, female, 0)

    total_voices = total_male + total_female
    
    print((total_voices, total_female, total_male))
    return (total_voices, total_female, total_male)