"""Functions for reading and writing EPANET input files.

This module provides functionality to read EPANET input files, parse their content,
and write EPANET input data back to files. It includes functions for preprocessing
lines, reading sections, and writing data in the correct format.

The EPANETFileIO class provides static methods for:
- Reading EPANET .inp files into OrderedDict structures
- Writing OrderedDict structures back to EPANET .inp files
- Preserving section order and formatting

EPANET input files are organized into sections marked by [SECTION_NAME] headers,
with data lines following each header.
"""
from typing import TextIO
import itertools
import string
import pathlib
import collections
from collections import OrderedDict
from rich import print as rprint
from ..auxiliary.utils import log


class EPANETFileReaderError(Exception):
    """Custom exception for EPANET file parsing errors.

    This exception is raised when there are errors parsing EPANET input files,
    such as invalid format, unexpected structure, or malformed sections.

    Parameters
    ----------
    message : str
        Description of the parsing error.

    Attributes
    ----------
    message : str
        The error message.

    Examples
    --------
    >>> raise EPANETFileReaderError("Expected '[', found: 'TITLE'")
    """
    def __init__(self, message: str):
        """Initialize the exception.

        Parameters
        ----------
        message : str
            Description of the parsing error.
        """
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Return string representation of the exception.

        Returns
        -------
        str
            Formatted error message with 'EPANET File Parser Error:' prefix.
        """
        return f'EPANET File Parser Error: {self.message}'
    
    def log(self) -> None:
        """Pretty-print the error using rich formatting.

        Prints the error message to console with red color formatting.
        """
        rprint(f"[red]EPANET File Parser Error:[/red] {self.message}")


class EPANETFileIO:
    """Collection of static methods for reading and writing EPANET input files.

    This class provides utilities for parsing EPANET .inp files and writing
    structured data back to the EPANET format. All methods are static and
    don't require instantiation.

    Methods
    -------
    read_file(path)
        Read an EPANET input file and return its contents as an OrderedDict.
    write_file(path, model_data)
        Write EPANET input data to a file.

    Notes
    -----
    The parser preserves the original section order from the input file and
    handles comments and blank lines automatically.
    """

    @staticmethod
    def read_inp_file(path: str | pathlib.Path) -> OrderedDict:
        """Read an EPANET input (INP) file and return its contents as an OrderedDict.

        Parameters
        ----------
        path : str or pathlib.Path
            Path to the EPANET input file.

        Returns
        -------
        OrderedDict
            Dictionary containing the EPANET input file contents.
            Keys are section names (without brackets), values are lists of
            tokenized lines (split by whitespace).

        Raises
        ------
        EPANETFileReaderError
            If the input file format is invalid (section header expected but not found).
        FileNotFoundError
            If the specified file does not exist.
        PermissionError
            If the file cannot be read due to permissions.

        Notes
        -----
        - Comments (lines starting with ';') are automatically removed
        - Blank lines are filtered out
        - Section order is preserved from the original file
        - Each section's data is stored as a list of lists (tokenized lines)

        Examples
        --------
        >>> data = EPANETFileIO.read_inp_file('model.inp')
        >>> print(data.keys())
        odict_keys(['TITLE', 'JUNCTIONS', 'PIPES', ...])
        """
        
        def _preprocess_input_lines(lines: list) -> list:
            """Preprocess lines from an EPANET input file.

            Removes comments and blank lines from the input.

            Parameters
            ----------
            lines : list
                List of lines from the EPANET input file.

            Returns
            -------
            list
                Preprocessed lines with comments and blank lines removed.
            """
            lines = map(
                lambda line : ''.join(
                    itertools.takewhile(lambda c : c not in ";\n\r", line)
                    ), lines
                )      # get rid of comments ...
            lines = filter(
                lambda line : any(
                    map(lambda c : c in string.printable, line)), lines
                )      # ... and blank lines
            return lines
        
        def _input_read(file_handle: TextIO) -> OrderedDict:
            """Read an EPANET input file and return its contents as an OrderedDict.

            Parameters
            ----------
            file_handle : TextIO
                File handle to an EPANET input file, must be opened in text mode.

            Returns
            -------
            OrderedDict
                Dictionary containing the EPANET input file contents.
                Keys are section names (without brackets),
                values are lists of tokenized lines (split by whitespace).

            Raises
            ------
            EPANETFileReaderError
                If the input file format is invalid
                (section header expected but not found).

            Notes
            -----
            The function preserves the original section order from the input file.
            Each section's data is stored as a list of lists, where each inner list
            contains the whitespace-separated tokens from one line.
            """
            lines = list(_preprocess_input_lines(file_handle.readlines()))
            nlines = len(lines)

            line_number = 0
            expect_header = True
            # NOTE: do not mess with section order!
            inp = collections.OrderedDict()
            while line_number < nlines:
                line = lines[line_number]
                if expect_header:
                    if line[0] == '[' and line[-1] == ']':
                        name = line[1:-1]
                        data = []
                        expect_header = False
                    else:
                        raise EPANETFileReaderError(
                            message=f"internal error: expected '[', found: '{line}'"
                        )
                else:
                    if line[0] == '[':
                        inp[name] = data
                        expect_header = True
                        line_number -= 1
                    else:
                        data.append(line.split())
                line_number += 1
            # remainder
            data = [element.strip() for element in data if element.strip()]
            if data:
                inp[name] = data
            return inp
        
        with open(path, 'r', encoding='utf-8') as file_handle:
            return _input_read(file_handle)

    @staticmethod
    def write_inp_file(path: str | pathlib.Path, model_data: OrderedDict) -> None:
        """Write EPANET input data to a file.

        Parameters
        ----------
        path : str or pathlib.Path
            Path to the output EPANET input file.
        model_data : OrderedDict
            Dictionary containing EPANET input data. Keys are section names,
            values are lists of tokenized lines.

        Notes
        -----
        - Each section is written with a [SECTION_NAME] header
        - Data lines are joined with spaces
        - Blank lines separate sections
        - File encoding is UTF-8

        Examples
        --------
        >>> data = OrderedDict([('TITLE', [['My', 'Network']]),
        ...                     ('JUNCTIONS', [['J1', '100']])])
        >>> EPANETFileIO.write_inp_file('output.inp', data)
        """
        
        def _input_write(file_handle: TextIO, model_data: OrderedDict) -> None:
            """Write EPANET input data to a file handle.

            Parameters
            ----------
            file_handle : TextIO
                File handle to write to (must be opened in text mode).
            model_data : OrderedDict
                Dictionary containing EPANET input data.
            """
            for name, lines in model_data.items():
                file_handle.write('[' + name + ']\n')
                for line in lines:
                    file_handle.write(' '.join(line) + '\n')
                file_handle.write('\n')
        
        with open(path, 'w', encoding='utf-8') as file_handle:
            _input_write(file_handle, model_data)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='EPANET Input File Parser')
    parser.add_argument('input_file', type=str, help='Path to the EPANET input file')
    parser.add_argument('output_file', type=str, help='Path to save the parsed output')
    args = parser.parse_args()
    # Read the EPANET file to a dictionary
    inp_data = EPANETFileIO.read_inp_file(args.input_file)
    # Write the dictionary back to EPANET file
    EPANETFileIO.write_inp_file(args.output_file, inp_data)
    log('INFO', f'Successfully parsed {args.input_file} and saved to {args.output_file}')
