import configparser
import subprocess
import shlex

from flask import Flask


# The main procedure:
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


def make_an_executor(command_string, working_dir):
    # Execution handler function used as a view
    def executor(arguments_as_path = None):

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

        # todo: there has to be some cleaner way to do it, deal with it later.
        # todo: add try catch, it may fail due to permission or something else.
        subprocess.call(['mkdir', '-p', working_dir])


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

        # todo: try catch, if this execution fails, an CalledProcessError will be raised.
        # todo: try catch, if the command is not there, an FileNotFoundError is raised.
        output = subprocess.check_output(
            command_and_args, cwd=working_dir, stdin=None, stderr=None, shell=False, universal_newlines=False)


        # Return the execution result.

        #   Note: The output string of subprocess's execution is a 'bytes' type. It's not a string, so we have to
        #    make it a string. And by default, of any text displayed in a browser, the whitespaces will be collapsed,
        #    and newline mark will be discarded, so we do not have the line-by-line display. To get it display properly,
        #    we have to give it some basic CSS hint, so the browser will not mess up the output.
        # todo: replace it with template for a cleaner implementation
        print(output)
        # output is a bytestream,so we have to transform it into a string using this trick.
        output = "<span style=\"white-space: pre-wrap\">"+"".join(map(chr, output))+"</span>"
        return output

    # return the function we just defined.
    return executor


### Read config files ###

# todo: try catch, if config file not exist or can't read properly, stop and exit.
# Use config parser to do the parse. config file is 'command_bind.conf'.
config = configparser.ConfigParser()


config.read('command_bind.conf')

# todo: try catch for every keywords, config files maybe compromised, and these keywords may not exist.
# Get some default values for later use.
# Get port number, used to tell flask which port to be on.
default_port_number = config.defaults()['port']

### Init the flask instance app ###
app = Flask(__name__)


### Iterate through all the sections and make binds ###

# For each section, read the mandatory and optional fields, setup an executor function, and make binds.
for section in config.sections():
    # Get the fields in this config section.

    # todo: try catch, if the config file is compromised and these mandatory fields are not there, raise an error.
    # Mandatory fields, they must be there or an error is raised and the program will stop.
    # todo: if command and http_keyword is empty string, stop the code, raise an error.
    command = config[section]['command']
    print('['+section+']' + ': command = ' + command)
    http_keyword = config[section]['http_keyword']
    print('[' + section + ']' + ': http_keyword = ' + http_keyword)

    # Optional fields.

    # working directory, if it's not there, use the value in DEFAULT.
    working_directory = config[section]['working_directory']
    print('[' + section + ']' + ': working_directory = ' + working_directory)


    # accept params or not, if it's not set, use the value in DEFAULT.
    accept_arguments = config.getboolean(section, 'accept_parameters')


    # Get an predefined executor function according the options we just parsed.

    # The command and working directory is already known in config time.
    # The arguments (if any) will be passed during runtime when we got one.
    executor = make_an_executor(command, working_directory)

    # If accept arguments, all the string following the keyword will be copied to a string with all the '/' unaltered.
    # It can be later parsed to a list with separator '/'. So we can pass  holding the options and arguments.
    # So if 'ls' is bind to '/listfiles', we can call 'ls -l' in this way: 'someIP:port/listfiles/-l'.
    if accept_arguments:
        print('['+section+']' + ': accept_arguments = true')
        route_string_with_args = '/' + http_keyword + '/<path:arguments_as_path>'
        print('[' + section + ']' + ': route_string_with_args = ' + route_string_with_args)
        app.route(route_string_with_args)(executor)

    # Just bind this function with the http_keyword as the path, with the param string empty.
    # No matter accept arguments or not, the no argument version of route should always be registered, or will be a 404.
    # The trailing '/' is to make sure if any trailing '/' exist following keyword, there will not be a 404.
    route_string_without_args = '/' + http_keyword + '/'
    app.route(route_string_without_args)(executor)
    print('[' + section + ']' + ': route_string_without_args = ' + route_string_without_args)


# Entry point of this module.

if __name__ == '__main__':
    app.run()
