#
# Chris Lumens <clumens@redhat.com>
#
# Copyright 2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""
Base classes for creating commands and syntax version object.

This module exports several important base classes:

    BaseData - The base abstract class for all data objects.  Data objects
               are contained within a BaseHandler object.

    BaseHandler - The base abstract class from which versioned kickstart
                  handler are derived.  Subclasses of BaseHandler hold
                  BaseData and KickstartCommand objects.

    DeprecatedCommand - A concrete subclass of KickstartCommand that should
                        be further subclassed by users of this module.  When
                        a subclass is used, a warning message will be
                        printed.

    KickstartCommand - The base abstract class for all kickstart commands.
                       Command objects are contained within a BaseHandler
                       object.
"""
from rhpl.translate import _
import rhpl.translate as translate

translate.textdomain("pykickstart")

import warnings
from pykickstart.errors import *
from pykickstart.parser import Packages

###
### COMMANDS
###
class KickstartCommand:
    """The base class for all kickstart commands.  This is an abstract class."""
    def __init__(self, writePriority=0):
        """Create a new KickstartCommand instance.  This method must be
           provided by all subclasses, but subclasses must call
           KickstartCommand.__init__ first.  Instance attributes:

           currentCmd    -- The name of the command in the input file that
                            caused this handler to be run.
           handler       -- A reference to the BaseHandler subclass this
                            command is contained withing.  This is needed to
                            allow referencing of Data objects.
           lineno        -- The current line number in the input file.
           writePriority -- An integer specifying when this command should be
                            printed when iterating over all commands' __str__
                            methods.  The higher the number, the later this
                            command will be written.  All commands with the
                            same priority will be written alphabetically.
        """

        # We don't want people using this class by itself.
        if self.__class__ is KickstartCommand:
            raise TypeError, "KickstartCommand is an abstract class."

        self.writePriority = writePriority

        # These will be set by the dispatcher.
        self.currentCmd = ""
        self.handler = None
        self.lineno = 0

    def __call__(self, *args, **kwargs):
        """Set multiple attributes on a subclass of KickstartCommand at once
           via keyword arguments.  Valid attributes are anything specified in
           a subclass, but unknown attributes will be ignored.
        """
        for (key, val) in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def __str__(self):
        """Return a string formatted for output to a kickstart file.  This
           method must be provided by all subclasses.
        """
        raise TypeError, "__str__() not implemented for KickstartCommand"

    def parse(self, args):
        """Parse the list of args and set data on the KickstartCommand object.
           This method must be provided by all subclasses.
        """
        raise TypeError, "parse() not implemented for KickstartCommand"

    # Set the contents of the opts object (an instance of optparse.Values
    # returned by parse_args) as attributes on the KickstartCommand object.
    # It's useful to call this from KickstartCommand subclasses after parsing
    # the arguments.
    def _setToSelf(self, optParser, opts):
        for key in filter (lambda k: getattr(opts, k) != None, optParser.keys()):
            setattr(self, key, getattr(opts, key))

    # Sets the contents of the opts object (an instance of optparse.Values
    # returned by parse_args) as attributes on the provided object obj.  It's
    # useful to call this from KickstartCommand subclasses that handle lists
    # of objects (like partitions, network devices, etc.) and need to populate
    # a Data object.
    def _setToObj(self, optParser, opts, obj):
        for key in filter (lambda k: getattr(opts, k) != None, optParser.keys()):
            setattr(obj, key, getattr(opts, key))

class DeprecatedCommand(KickstartCommand):
    """Specify that a command is deprecated and no longer has any function.
       Any command that is deprecated should be subclassed from this class,
       only specifying an __init__ method that calls the superclass's __init__.
    """
    def __init__(self, writePriority=None):
        """Create a new DeprecatedCommand instance."""
        KickstartCommand.__init__(self, writePriority)

    def __str__(self):
        """Placeholder since DeprecatedCommands don't work anymore."""
        return ""

    def parse(self, args):
        """Print a warning message if the command is seen in the input file."""
        mapping = {"lineno": self.lineno, "cmd": self.currentCmd}
        warnings.warn(_("Ignoring deprecated command on line %(lineno)s:  The %(cmd)s command has been deprecated and no longer has any effect.  It may be removed from future releases, which will result in a fatal error from kickstart.  Please modify your kickstart file to remove this command.") % mapping, DeprecationWarning)

###
### HANDLERS
###
class BaseHandler:
    """Each version of kickstart syntax is provided by a subclass of this
       class.  These subclasses are what users will interact with for parsing,
       extracting data, and writing out kickstart files.  This is an abstract
       class.
    """
    def __init__(self):
        """Create a new BaseHandler instance.  This method must be provided by
           all subclasses, but subclasses must call BaseHandler.__init__ first.
           Instance attributes:

           commands -- A mapping from a string command to a KickstartCommand
                       subclass object that handles it.  Multiple strings can
                       map to the same object, but only one instance of the
                       handler object should ever exist.  Most users should
                       never have to deal with this directly, as it is
                       manipulated through registerCommand and dispatcher.
           packages -- An instance of pykickstart.parser.Packages which
                       describes the packages section of the input file.
           platform -- A string describing the hardware platform, which is
                       needed only by system-config-kickstart.
           scripts --  A list of pykickstart.parser.Script instances, which is
                       populated by KickstartParser.addScript and describes the
                       %pre/%post/%traceback script section of the input file.
        """

        # We don't want people using this class by itself.
        if self.__class__ is BaseHandler:
            raise TypeError, "BaseHandler is an abstract class."

        self.commands = {}

        # This isn't really a good place for these, but it's better than
        # everything else I can think of.
        self.scripts = []
        self.packages = Packages()
        self.platform = ""

        # A dict keyed by an integer priority number, with each value being a
        # list of KickstartCommand subclasses.  This dict is maintained by
        # registerCommand and used in __str__.  No one else should be touching
        # it.
        self._writeOrder = {}

    def __str__(self):
        """Return a string formatted for output to a kickstart file."""
        retval = ""

        if self.platform != "":
            retval += "#platform=%s\n" % self.platform

        lst = self._writeOrder.keys()
        lst.sort()

        for prio in lst:
            for obj in self._writeOrder[prio]:
                retval += obj.__str__()

        for script in self.scripts:
            retval += script.__str__()

        retval += self.packages.__str__()

        return retval

    def _insertSorted(self, list, obj):
        max = len(list)
        i = 0

        while i < max:
            # If the two classes have the same name, it's because we are
            # overriding an existing class with one from a later kickstart
            # version, so remove the old one in favor of the new one.
            if obj.__class__.__name__ > list[i].__class__.__name__:
                i += 1
            elif obj.__class__.__name__ == list[i].__class__.__name__:
                list[i] = obj
                return
            elif obj.__class__.__name__ < list[i].__class__.__name__:
                break

        if i >= max:
            list.append(obj)
        else:
            list.insert(i, obj)

    def _setCommand(self, cmdObj):
        # Add an attribute on this version object.  We need this to provide a
        # way for clients to access the command objects.
        setattr(self, cmdObj.__class__.__name__.lower(), cmdObj)

        # Also, add the object into the _writeOrder dict in the right place.
        if cmdObj.writePriority is not None:
            if self._writeOrder.has_key(cmdObj.writePriority):
                self._insertSorted(self._writeOrder[cmdObj.writePriority], cmdObj)
            else:
                self._writeOrder[cmdObj.writePriority] = [cmdObj]

    def dispatcher(self, cmd, cmdArgs, lineno):
        """Given the command string cmd and the list of arguments cmdArgs, call
           the appropriate KickstartCommand handler that has been previously
           registered.  lineno is needed for error reporting.  If cmd does not
           exist in the commands dict, KickstartParseError will be raised.  A
           handler of None for the given command is not an error.
        """
        if not self.commands.has_key(cmd):
            raise KickstartParseError, formatErrorMsg(lineno, msg=_("Unknown command: %s" % cmd))
        else:
            if self.commands[cmd] != None:
                self.commands[cmd].currentCmd = cmd
                self.commands[cmd].handler = self
                self.commands[cmd].lineno = lineno
                self.commands[cmd].parse(cmdArgs)

    def empty(self):
        """Set all entries in the commands dict to None so no commands
           will be processed.
        """
        self._writeOrder = {}

        for (key, val) in self.commands.iteritems():
            self.commands[key] = None

    def hasCommand(self, cmd):
        """Return true if there is a handler for the string cmd."""
        return hasattr(self, cmd)

    def overrideCommand(self, cmdObj):
        """Override an existing mapping with a new instance of a command
           handler class.  There must already be a mapping from at least one
           string command to a command object as set up by registerCommand,
           as this method looks for instances with the same class name as
           cmdObj to replace.
        """
        found = False

        # We have to update all the entries in the commands dict with a
        # reference to the new handler.
        for (key, val) in self.commands.iteritems():
            if val.__class__.__name__ == cmdObj.__class__.__name__:
                found = True
                self.commands[key] = cmdObj

        if found:
            self._setCommand(cmdObj)

    def registerCommand(self, cmdObj, cmdList):
        """Set up a mapping from each string command in cmdList to the instance
           of the KickstartCommand subclass object cmdObj.  Using a list of
           commands allows for aliasing commands to each other.  Also create a
           new attribute on this BaseHandler subclass named
           cmdObj.__class__.__name__ with a value of cmdObj.
        """
        # Add the new command object to the dict for all given command strings.
        for str in cmdList:
            self.commands[str] = cmdObj

        self._setCommand(cmdObj)

    def unregisterCommand(self, cmdObj):
        """Remove support for a command from this handler instance.  The
           parameter cmdObj is a command handler class (not an instance) that
           should be removed.  This removes support for all string commands
           that map to cmdObj, as well as support for writing it and calling
           it on the handler.  The most common use for this method is to
           remove commands that were deprecated in a previous version.
        """
        # First remove any keys in the commands dict that map to an instance
        # of the given command object.
        for (key, val) in self.commands.items():
            if val.__class__.__name__ == cmdObj.__name__:
                self.commands.pop(key)

        # Then remove any keys in the _writeOrder dict that do the same.  To
        # do this we have to search each list in _writeOrder and remove any
        # with a matching name.  Then if that was the only command in that
        # list, we should remove the key entirely.
        for (key, val) in self._writeOrder.items():
            for ele in val:
                if ele.__class__.__name__ == cmdObj.__name__:
                    val.remove(ele)
                    break

            if len(val) == 0:
                del(self._writeOrder[key])

        # Finally, remove the attribute on the handler object itself.
        delattr(self, cmdObj.__name__.lower())

###
### DATA
###
class BaseData:
    """The base class for all data objects.  This is an abstract class."""
    def __init__(self):
        """Create a new BaseData instance.  There are no attributes."""

        # We don't want people using this class by itself.
        if self.__class__ is BaseData:
            raise TypeError, "BaseData is an abstract class."

    def __str__(self):
        """Return a string formatted for output to a kickstart file."""
        return ""

    def __call__(self, *args, **kwargs):
        """Set multiple attributes on a subclass of BaseData at once via
           keyword arguments.  Valid attributes are anything specified in a
           subclass, but unknown attributes will be ignored.
        """
        for (key, val) in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)