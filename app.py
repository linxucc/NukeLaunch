import configparser
import subprocess
import shlex
import getpass
import os.path
import socket

from flask import Flask, render_template

# Default settings:

# The port number to listen on:
port_number = 8095
# Host settings, set to 0.0.0.0 by default to allow all the external access.
# Since most times, this program is supposed to be running in a local network, so it's OK to make it simple.
# If in your case, it's not OK to make the service public, set the address accordingly.
host_address = '0.0.0.0'
# Default config file, set to the 'command_bind.conf' by default, relative to program's folder.
# If the config file is not in the same folder, you have to specify the full absolute path.
config_file_name_with_full_path = 'command_bind.conf'



# The main procedures:
# 1. Read the config file, check minimum integrity, set the defaults.
# 2. Loop through all the sections in the config file, for each section entry, make a handler function for it,
#  then register it with the http route path '/http_keyword_for_this_command/'.
# 3. Run this app, start the http server.

# The execution handler, how it works:
# 1. The [command] and [working directory] is set during the config time.
# 2. The [arguments] (if any) will be passed in during the runtime, when a matching http call is processed by flask,
#   flask will pass the arguments (if any) as a path string to the matching handler function.
# 3. We use [subprocess] module to execute the command and receive its output.
# 4. Since the subprocess will only take command and all arguments in, with a form of a list of strings,
#   so we have to slice the command and arguments string into list, concatenate it, then feed it to subprocess call.
# 5. When the subprocess execution finished, we render the output into a simple html template, and return it
#   as a http response.



'''Factory function to generate execution handler functions for each command.'''


# Note: We use a factory to generate actual functions to execute the command and bind with keyword.
# The function returned by this function, will be decorated later with the path we configured in the config file.
# We define the main command execution procedures here, so that it is separated with other stuff.


def make_an_executor(section_name, command_string, working_dir, mkdir_yn):
    # Execution handler function used as a view
    def executor(arguments_as_path=None):
        # Error message string. Also used to keep a state of the execution.
        # Initially it's empty, empty = no error,
        #   were there any error, error info writes into it and it's no more empty, we know things has happened.
        error_message = ''

        # The state of the execution.
        # Initially, it's false, only when the command execution is successful (return code=0), this becomes True.
        execute_success = False

        # The current user, this information sometimes is important to find out what's going wrong.
        os_user_name = getpass.getuser()
        # Get current host name, used to display a UNIX terminal style message to user.
        try:
            host_name = socket.gethostname()
        except:
            host_name = "Unknown_host"

            # Process of incoming argument string, translate the path style params to an list of arguments.

        argument_list = []
        # If path arguments exist, and it's not empty, we parse arguments_as_path from string to an list.
        if arguments_as_path:
            # argument list, we get this list through the split() function of string, with '/' as separator.
            argument_list = arguments_as_path.split('/')
            print(argument_list)
        # If path arguments do not exist or is empty, there will be no arguments, we do nothing.
        else:
            # provide an empty argument_list, so the programs below can use this variable safely.
            pass

        # Check if working directory exist, if not, create it.
        if os.path.exists(working_dir):
            if os.path.isfile(working_dir):
                # Working dir exist but it's not a directory, raise an error.
                error_message = 'The working directory ' + working_dir + ' exists, and it\'s not a directory, ' \
                                                                         'please check the configs'
                return error_message
            else:
                # working dir exists, and it's a directory, no need to do anything
                pass
        else:
            # working directory does not exist, check the mkdir_yn tag to see if we have to auto create it.
            if mkdir_yn:
                # Directory does not exist, and auto-create is on, create it.
                try:
                    os.makedirs(working_dir)
                except OSError as e:
                    error_message = 'Your working directory ' + \
                                    working_dir + ' does not exist, try to mkdir due to ' \
                                                  'your config, but failed. Maybe a ' \
                                                  'permission problem? Current user: ' + os_user_name + '\n\n' + \
                                    + e.strerror
                    return error_message

            else:
                # Directory does not exist, and auto-create is off, an error should be raised.
                error_message = 'Your working directory ' + \
                                working_dir + ' does not exist, and you disabled auto-create.' \
                                + 'Please check your working directory settings, make sure it exists,' \
                                  ' or enable auto-create.'
                return error_message

        # old version, replaced by above.
        # subprocess.call(['mkdir', '-p', working_dir])

        # Slice the original command string to a list, so if there's any pre-defined argument, we can handle properly.

        #   WHY: commands like 'ls -l' will be taken as the name of the executable, if we pass it directly
        #    to subprocess's execution functions. And it will fail due to the executable with the name of 'ls -l'
        #    is not exist at all! So we use shlex to slice the command to a list that can be understand properly by
        #    subprocess's mechanism.

        command_and_args = shlex.split(command_string)

        # Append the argument list to the command_and_args list. So if there's any incoming arguments, it will be added.

        command_and_args = command_and_args + argument_list
        print(command_and_args)

        # The final execution of the command we just put together.

        output_string = ''
        try:
            # For a detailed explanation on [passing string or sequence] to subprocess calls, check this link:
            # https://stackoverflow.com/questions/15109665/subprocess-call-using-string-vs-using-list
            # Simply put, if shell=False, use sequnce, the first string in sequence will be the command, others ars.
            # If shell=True, use string, or the first string in the seq will be the command, and all the others will
            #   be treated as additional arguments to the shell itself.
            output_raw = subprocess.check_output(
                command_and_args, cwd=working_dir, stdin=None, stderr=subprocess.STDOUT, shell=False,
                universal_newlines=False)
            # output is a bytestream,so we have to transform it into a string using this trick.
            output_string = "".join(map(chr, output_raw))
            output_string.strip()
        except FileNotFoundError:
            error_message = 'Command or executable \'' + command_and_args[0] + \
                            '\' does not exist, check your config, and make sure the executable is accessible' \
                            ' in your working directory'
            return error_message
        except subprocess.CalledProcessError as execution_error:
            error_message = 'Command \'' + ' '.join(command_and_args) + '\' exit with an error.\n'
            error_code = execution_error.returncode
            output_string = str(execution_error.output)
            print(execution_error.output)

        # Return the execution result.

        #   Note: The output string of subprocess's execution is a 'bytes' type. It's not a string, so we have to
        #    make it a string. And by default, of any text displayed in a browser, the whitespaces will be collapsed,
        #    and newline mark will be discarded, so we do not have the line-by-line display. To get it display properly,
        #    we have to give it some basic CSS hint, so the browser will not mess up the output.

        # The tempalte should display these infomations:
        #   the final command, the user, the working dir, the result(status), the output (stdout,stderr),
        #   error message if status is not OK (besides stderr, when other excpetion is raised, we should translate it).
        #
        ##print(output_raw)

        command_final_string = " ".join(str(x) for x in command_and_args)
        command_final_string.strip()

        print(output_string)
        print(command_final_string)

        if error_message:
            status = "Fail" + " (ret = " + str(error_code) + " )"
        else:
            status = "OK"

        return render_template("output_display.html",
                               section_name=section_name,
                               command=command_final_string,
                               status=status,
                               username=os_user_name,
                               host_name=host_name,
                               working_dir=working_dir,
                               output=output_string,
                               error_message=error_message)
        # return output_string

    # Change the name of handler function to section name, to avoid name collision when Flask makes the route mapping.
    executor.__name__ = section_name
    # return the function we just defined.
    return executor


### Read config files ###

# Use config parser to do the parse. config file is 'command_bind.conf'.
config = configparser.ConfigParser(inline_comment_prefixes="#")

# Due to document, config.read returns a list of file names which were successfully parsed,
# so if it's empty, an error should be raised.
config_file_name_in_use = config.read(config_file_name_with_full_path)
if not config_file_name_in_use:
    # no file be parsed, raise an error, stop the code from init.
    print("No config file was found, or the config file is empyt or compromised, please check the config files.")
    raise SystemExit(1)

print("Config file: " + " ".join(config_file_name_in_use) + " opened successfully, parsing configs.\n")

# Assert all the optional config fields have value.
# All optional fields should have a default value, or there will be undefined behaviours.
print("Parsing [DEFAULT] section: \n")

try:
    default_working_directory = config.defaults()['working_directory']
    print("[default_working_directory]: " + default_working_directory)
    default_mkdir_if_working_directory_not_exist = config.defaults()['mkdir_if_working_directory_not_exist']
    print("[default_mkdir_if_working_directory_not_exist]: " + default_mkdir_if_working_directory_not_exist)
    default_accept_arguments = config.defaults()['accept_arguments']
    print("[default_accept_arguments]: " + default_accept_arguments)
except KeyError as e:
    print("Error: Config file is incomplete, default value for optional fields not found.")
    print("Missing key: '" + e.args[0] + "'")
    raise SystemExit(1)

print("\nDefault options parsed SUCCESSFULLY.\n")

### Init the flask instance app ###
app = Flask(__name__)

### Iterate through all the sections and make binds ###

print("Parsing keyword sections:")

# For each section, read the mandatory and optional fields, setup an executor function, and make binds.
for section in config.sections():
    print('\nSection: [' + section + ']\n')
    # Get the fields in this config section.

    # Mandatory fields, they must be there or an error is raised and the program will stop.
    try:
        command = config[section]['command']
    except KeyError:
        # If there's no command, since we are fetching the value by key, a KeyError will be raised.
        print("Error: Mandatory field 'command' not found in section '" + section + "', " +
                "please check the config file and try again")
        # Print the error, and exit the code with a return code of 1.
        raise SystemExit(1)

    print('[' + section + ']' + ': command = ' + command)
    # Directly use the section name as "http_keyword" for a more concise way to config.
    # The variable name "http_keyword" will still be used, for the rest part of the code could stay unchanged.
    http_keyword = section
    print('[' + section + ']' + ': http_keyword = ' + http_keyword)

    # Optional fields.

    # All optional fields is asserted to have default values in the DEFAULT section,
    #  And if there's no optional field key in section, the default value will be used.
    #  So there's no need to try-catch the KeyError exceptions here.

    # working directory, if it's not there, use the value in DEFAULT.
    working_directory = config[section]['working_directory']
    print('[' + section + ']' + ': working_directory = ' + working_directory)

    # whether mkdir or not if working directory does not exist during runtime.
    mkdir_if_working_directory_not_exist = config.getboolean(section, 'mkdir_if_working_directory_not_exist')
    print('[' + section + ']' + ': mkdir_if_working_directory_not_exist = ' + str(mkdir_if_working_directory_not_exist))

    # accept params or not, if it's not set, use the value in DEFAULT.
    accept_arguments = config.getboolean(section, 'accept_arguments')

    # Get an predefined executor function according the options we just parsed.

    # The command and working directory is already known in config time.
    # Flask asks for an unique name for each view function, because it use function names to handle the route,mapping,
    #   so section name will be the function name so there's no collision.
    # That's why we need section name, command, working_directory to make a execution handler.
    # The arguments (if any) will be passed during runtime when we got one.
    executor = make_an_executor(section, command, working_directory, mkdir_if_working_directory_not_exist)

    # If accept arguments, all the string following the keyword will be copied to a string with all the '/' unaltered.
    # It can be later parsed to a list with separator '/'. So we can pass  holding the options and arguments.
    # So if 'ls' is bind to '/listfiles', we can call 'ls -l' in this way: 'someIP:port/listfiles/-l'.
    if accept_arguments:
        print('[' + section + ']' + ': accept_arguments = true')
        route_string_with_args = '/' + http_keyword + '/<path:arguments_as_path>'
        print('[' + section + ']' + ': route_string_with_args = ' + route_string_with_args)
        app.route(route_string_with_args)(executor)

    # Just bind this function with the http_keyword as the path, with the param string empty.
    # No matter accept arguments or not, the no argument version of route should always be registered, or will be a 404.
    # The trailing '/' is to make sure if any trailing '/' exist following keyword, there will not be a 404.
    route_string_without_args = '/' + http_keyword + '/'
    app.route(route_string_without_args)(executor)
    print('[' + section + ']' + ': route_string_without_args = ' + route_string_without_args)

    print('[' + section + ']' + ': Command and route registered SUCCESSFULLY.\n')

# Entry point of this module.
print('Port number: ' + str(port_number))
print('Host IP: ' + str(port_number))

if __name__ == '__main__':
    app.run(port=port_number, host=host_address, debug=False)
