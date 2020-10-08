# Autopsy Speech to Text
# Copyright 2020 Miguel Negrao.

# Autopsy Speech to Text: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Autopsy Speech to Text is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Autopsy Speech to Text.  If not, see <http://www.gnu.org/licenses/>.

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