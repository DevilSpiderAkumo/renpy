﻿# Copyright 2004-2025 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

init -1500 python:

    @renpy.pure
    class InvertSelected(Action, DictEquality):
        """
        :doc: other_action

        This inverts the selection state of the provided action, while
        proxying over all of the other methods.
        """

        def __init__(self, action):
            self.action = action

            try:
                self.alt = action.alt
            except Exception:
                pass

        def __call__(self):
            return self.action.__call__()

        def get_selected(self):
            return not self.action.get_selected()

        def get_sensitive(self):
            return self.action.get_sensitive()

        def periodic(self, st):
            return self.action.periodic(st)

        def predict(self):
            self.action.predict()

    @renpy.pure
    def If(expression, true=None, false=None):
        """
        :doc: other_action action

        This returns `true` if `expression` is true, and `false`
        otherwise. Use this to select an action based on an expression.
        Note that the default, None, can be used as an action that causes
        a button to be disabled.
        """

        if expression:
            return true
        else:
            return false


    class _ActionList(Action, DictEquality):
        """
        :undocumented:

        Encapsulates a list of actions, so that they can be treated as a single action,
        for the purposes of SelectedIf and SensitiveIf.
        """

        def __init__(self, actions):
            self.actions = actions

        def get_selected(self):
            return renpy.display.behavior.is_selected(self.actions)

        def get_sensitive(self):
            return renpy.display.behavior.is_sensitive(self.actions)

        def get_tooltip(self):
            return renpy.display.behavior.get_tooltip(self.actions)

        def periodic(self, st):
            return renpy.display.behavior.run_periodic(self.actions, st)

        def unhovered(self):
            return renpy.display.behavior.run_unhovered(self.actions)

        def __call__(self):
            return renpy.run(self.actions)


    @renpy.pure
    class SelectedIf(Action, DictEquality):
        """
        :doc: other_action
        :args: (action, /)

        This indicates that one action in a list of actions should be used
        to determine if a button is selected. This only makes sense
        when the button has a list of actions. For example::

            # The button is selected only if mars_flag is True
            textbutton "Marsopolis":
                action [ SelectedIf(SetVariable("mars_flag", True)), SetVariable("on_mars", True) ]

        The action inside SelectedIf is run normally when the button is clicked.
        """

        # Note: This had been documented to take a boolean.

        def __init__(self, expression):
            if isinstance(expression, (list, tuple)):
                expression = _ActionList(expression)

            self.expression = expression

            if isinstance(expression, Action):
                for i in ("get_selected", "get_sensitive", "get_tooltip", "periodic", "unhovered", "alt"):
                    setattr(self, i, getattr(expression, i, None))

        def __call__(self):
            if isinstance(self.expression, Action):
                return self.expression()
            return None

        def get_selected(self):
            return self.expression

    @renpy.pure
    class SensitiveIf(Action, DictEquality):
        """
        :doc: other_action
        :args: (action, /)

        This indicates that one action in a list of actions should be used
        to determine if a button is sensitive. This only makes sense
        when the button has a list of actions. For example::

            # The button is sensitive only if mars_flag is True
            textbutton "Marsopolis":
                action [ SensitiveIf(SetVariable("mars_flag", True)), SetVariable("on_mars", True) ]

        The action inside SensitiveIf is run normally when the button is clicked.
        """

        # Note: This had been documented to take a boolean.

        def __init__(self, expression):
            if isinstance(expression, (list, tuple)):
                expression = _ActionList(expression)

            self.expression = expression

            if isinstance(expression, Action):
                for i in ("get_selected", "get_sensitive", "get_tooltip", "periodic", "unhovered", "alt"):
                    setattr(self, i, getattr(expression, i, None))

        def __call__(self):
            if isinstance(self.expression, Action):
                return self.expression()
            return None

        def get_sensitive(self):
            return self.expression

    @renpy.pure
    class Screenshot(Action, DictEquality):
        """
        :doc: other_action

        Takes a screenshot.
        """

        def __call__(self):
            _screenshot()

    @renpy.pure
    class HideInterface(Action, DictEquality):
        """
        :doc: other_action

        Causes the interface to be hidden until the user clicks.
        This is typically what happens when hitting the H key in a Ren'Py game.
        """

        def __call__(self):
            renpy.call_in_new_context("_hide_windows")


    @renpy.pure
    class OpenURL(Action, DictEquality):
        """
        :doc: other_action

        Causes `url` to be opened in a web browser.
        """

        def __init__(self, url):
            self.url = url

        def __call__(self):
            renpy.open_url(self.url)

    class With(Action, DictEquality):
        """
        :doc: other_action

        Causes `transition` to occur.
        """

        def __init__(self, transition):
            self.transition = transition

        def __call__(self):
            renpy.transition(self.transition)
            renpy.restart_interaction()

    @renpy.pure
    class Notify(Action, DictEquality):
        """
        :doc: other_action

        Displays `message` using :func:`renpy.notify`.
        """

        def __init__(self, message):
            self.message = message

        def predict(self):
            renpy.predict_screen("notify")

        def __call__(self):
            renpy.notify(self.message)

    @renpy.pure
    class Rollback(Action, DictEquality):
        """
        :doc: other_action
        :args: (*args, force="menu", **kwargs)

        This action causes a rollback to occur, when a rollback is possible.
        Otherwise, nothing happens.

        The arguments are given to :func:`renpy.rollback`. This includes the
        `force` argument which here defaults to "menu".
        """

        args = tuple()
        kwargs = { "force" : "menu" }

        def __init__(self, *args, **kwargs):
            self.args = args
            kwargs.setdefault("force", "menu")
            self.kwargs = kwargs

        def __call__(self):
            renpy.rollback(*self.args, **self.kwargs)

        def get_sensitive(self):
            return renpy.can_rollback()

    class RollbackToIdentifier(Action, DictEquality):
        """
        :doc: other_action

        This causes a rollback to an identifier to occur. Rollback
        identifiers are returned as part of HistoryEntry objects.
        """

        def __init__(self, identifier):
            self.identifier = identifier

        def __call__(self):
            checkpoints = renpy.get_identifier_checkpoints(self.identifier)

            if checkpoints is not None:
                renpy.rollback(checkpoints=checkpoints, force="menu")

        def get_sensitive(self):
            return (renpy.get_identifier_checkpoints(self.identifier) is not None)

    @renpy.pure
    class RestartStatement(Action, DictEquality):
        """
        :doc: other_action

        This action causes Ren'Py to rollback to before the current
        statement, and then re-run the current statement. This may be used
        when changing a persistent variable that affects how the statement
        is displayed.

        If run in a menu context, this waits until the player exits to a
        top-level context before performing the rollback.
        """

        def __call__(self):
            renpy.rollback(force=True, checkpoints=0, defer=True)

    @renpy.pure
    class RollForward(Action, DictEquality):
        """
        :doc: other_action

        This action causes a rollforward to occur, if a roll forward is
        possible. Otherwise, it is insensitive.
        """

        def __call__(self):
            return renpy.exports.roll_forward_core()

        def get_sensitive(self):
            return renpy.roll_forward_info() is not None


    #########################################################################

    def GetTooltip(screen=None, last=False):
        """
        :doc: get_tooltip

        Returns the tooltip of the currently focused displayable, or None
        if no displayable is focused.

        `screen`
            If not None, this should be the name or tag of a screen. If
            given, this function only returns the tooltip if the focused
            displayable is part of the screen.

        `last`
            If true, returns the last non-None value this function would
            have returned.
        """

        return renpy.display.focus.get_tooltip(screen, last)


    class __TooltipAction(Action, FieldEquality):

        identity_fields = [ "tooltip", "value" ]

        def __init__(self, tooltip, value):
            self.tooltip = tooltip
            self.value = value

        def __call__(self):
            if self.tooltip.value != self.value:
                self.tooltip.value = self.value
                renpy.restart_interaction()

        def unhovered(self):
            if self.tooltip.value != self.tooltip.default:
                self.tooltip.value = self.tooltip.default
                renpy.restart_interaction()

    _m1_00screen__TooltipAction = __TooltipAction


    class Tooltip(object):
        """
        :doc: tooltips class

        A tooltip object can be used to define a portion of a screen that is
        updated when the mouse hovers an area.

        A tooltip object has a ``value`` field, which is set to the `default`
        value passed to the constructor when the tooltip is created. When
        a button using an action created by the tooltip is hovered, the
        value field changes to the value associated with the action.
        """

        def __init__(self, default):
            self.value = default
            self.default = default

        def Action(self, value):
            """
            :doc: tooltips method
            :name: Action

            Returns an action that is generally used as the hovered property
            of a button. When the button is hovered, the value field of this
            tooltip is set to `value`. When the button loses focus, the
            value field of this tooltip reverts to the default.
            """

            return __TooltipAction(self, value)

        action = Action


    #########################################################################

    @renpy.pure
    class Language(Action, DictEquality):
        """
        :doc: language_action

        Changes the language of the game to `language`.

        `language`
            A string giving the language to translate to, or None to use
            the default language of the game script.
        """

        alt = _("Language [text]")

        def __init__(self, language):
            self.language = language

        def __call__(self):
            renpy.change_language(self.language)

        def get_selected(self):
            return _preferences.language == self.language

        def get_sensitive(self):
            if self.language is None:
                return True

            return self.language in renpy.known_languages()


    #########################################################################

    # Transitions used when entering and leaving replays.
    config.enter_replay_transition = None
    config.exit_replay_transition = None

    @renpy.pure
    class Replay(Action, DictEquality):
        """
        :doc: replay

        An action that starts `label` as a replay.

        `scope`
            A dictionary mapping variable name to value. These variables are set
            when entering the replay.

        `locked`
            If true, this action is insensitive and will not do anything when triggered.
            If false, it will behave normally. If None, it will be locked if the label
            has not been seen in any playthrough.
        """

        def __init__(self, label, scope={}, locked=None):
            self.label = label
            self.scope = scope
            self.locked = locked

        def __call__(self):

            if not self.get_sensitive():
                return

            if config.enter_replay_transition:
                renpy.transition(config.enter_replay_transition)

            renpy.call_replay(self.label, self.scope)

            if config.exit_replay_transition:
                renpy.transition(config.exit_replay_transition)

        def get_sensitive(self):
            if self.locked is not None:
                return not self.locked

            return renpy.seen_label(self.label)

    @renpy.pure
    class EndReplay(Action, DictEquality):
        """
        :doc: replay

        Ends the current replay.

        `confirm`
            If true, prompts the user for confirmation before ending the
            replay.
        """
        def __init__(self, confirm=True):
            self.confirm = confirm

        def __call__(self):

            if not self.get_sensitive():
                return

            if self.confirm:
                layout.yesno_screen(layout.END_REPLAY, EndReplay(False))
            else:
                renpy.end_replay()

        def get_sensitive(self):
            return _in_replay

    @renpy.pure
    class MouseMove(Action, DictEquality):
        """
        :doc: other_action

        Move the mouse pointer to `x`, `y`. If the device does not have a mouse
        pointer, if it is not possible for Ren'Py to move that pointer,
        or if the :var:`"automatic move" preference <preferences.mouse_move>`
        is False, this does nothing.

        This is unlikely to work on the Linux with Wayland, Android, iOS, or Web
        platforms.

        `duration`
            The time it will take to perform the move, in seconds. During
            this time, the mouse may be unresponsive.
        """
        def __init__(self, x, y, duration=0):
            self.x = x
            self.y = y
            self.duration = duration

        def __call__(self):
            if _preferences.mouse_move:
                renpy.set_mouse_pos(self.x, self.y, self.duration)


    @renpy.pure
    class QueueEvent(Action, DictEquality):
        """
        :doc: other_action

        Queues the given event using :func:`renpy.queue_event`.
        """

        def __init__(self, event, up=False):
            self.event = event
            self.up = up

        def __call__(self):
            renpy.queue_event(self.event, up=self.up)

    @renpy.pure
    class Function(Action):
        """
        :doc: other_action
        :args: (callable, *args, _update_screens=True, **kwargs)

        This Action calls ``callable(*args, **kwargs)``.

        `callable`
            Callable object. This assumes that if two callables compare
            equal, calling either one will be equivalent.

        `args`
            positional arguments to be passed to `callable`.

        `kwargs`
            keyword arguments to be passed to `callable`.

        `_update_screens`
            When true, the interaction restarts and the screens are updated
            after the function returns.

        If the function returns a non-None value, the interaction stops and
        returns that value. (When called using the call screen statement, the
        result is placed in the `_return` variable.)

        Instead of using a Function action, you can define your own subclass
        of the :class:`Action` class. This lets you name the action, and
        determine when it should be selected and sensitive.
        """

        update_screens = True

        def __eq__(self, other):
            if type(self) is not type(other):
                return False

            if self.callable != other.callable:
                return False

            if self.args != other.args:
                return False

            if self.kwargs != other.kwargs:
                return False

            for a, b in zip(self.args, other.args):
                if a is not b:
                    return False

            for k in self.kwargs:
                if self.kwargs[k] is not other.kwargs[k]:
                    return False

            if self.update_screens != other.update_screens:
                return False

            return True

        def __init__(self, callable, *args, **kwargs):
            self.callable = callable
            self.args = args

            self.update_screens = kwargs.pop("_update_screens", True)

            self.kwargs = kwargs

        def __call__(self):
            rv = self.callable(*self.args, **self.kwargs)

            if self.update_screens:
                renpy.restart_interaction()

            return rv

    @renpy.pure
    class Confirm(Action, DictEquality):
        """
        :doc: other_action

        Prompts the user for confirmation of an action. If the user
        clicks yes, the yes action is performed. Otherwise, the `no`
        action is performed.

        `prompt`
            The prompt to display to the user.

        `confirm_selected`
            If true, the prompt will be displayed even if the `yes` action
            is already selected. If false (the default), the prompt
            will not be displayed if the `yes` action is selected.

        Additional keyword arguments not beginning with _ are passed to
        the screen.

        The sensitivity and selectedness of this action match those
        of the `yes` action.

        See :func:`renpy.confirm` for a function version of this action.
        """


        kwargs = { }

        def __init__(self, prompt, yes, no=None, confirm_selected=False, **kwargs):
            self.prompt = prompt
            self.yes = yes
            self.no = no
            self.confirm_selected = confirm_selected
            self.kwargs = kwargs

        def __call__(self):
            if self.get_selected() and not self.confirm_selected:
                return renpy.run(self.yes)

            return layout.yesno_screen(self.prompt, self.yes, self.no, **self.kwargs)

        def get_sensitive(self):
            if self.yes is None:
                return False

            return renpy.is_sensitive(self.yes)

        def get_selected(self):
            return renpy.is_selected(self.yes)

        def get_tooltip(self):
            return renpy.display.behavior.get_tooltip(self.yes)

    @renpy.pure
    class Scroll(Action, DictEquality):
        """
        :doc: other_action

        Causes a Bar, Viewport, or Vpgrid to scroll.

        `id`
            The id of a bar, viewport, or vpgrid in the current screen.

        `direction`
            For a vbar, one of "increase" or "decrease". For a viewport
            or vpgrid, one of "horizontal increase", "vertical increase",
            "horizontal decrease", or "vertical decrease".

        `amount`
            The amount to scroll by. This can be a number of pixels, or
            else "step" or "page".

        `delay`
            If non-zero, the scroll will be animated for this many seconds.

        `time_warp`
            The easing function used for the scroll action. For example,
            the `ease` warper would be represented as `_warper.ease`
        """

        delay = 0.0

        def __init__(self, id, direction, amount="step", delay=0.0, time_warp=_warper.ease):
            self.id = id
            self.direction = direction
            self.amount = amount
            self.delay = delay
            self.time_warp = time_warp

        def get_adjustment_and_delta(self):

            d = renpy.get_widget(None, self.id)
            if d is None:
                return None, +1

            if self.direction == "increase":
                delta = +1
                adjustment = d.adjustment
            elif self.direction == "decrease":
                delta = -1
                adjustment = d.adjustment
            elif self.direction == "horizontal increase":
                delta = +1
                adjustment = d.xadjustment
            elif self.direction == "horizontal decrease":
                delta = -1
                adjustment = d.xadjustment
            elif self.direction == "vertical increase":
                delta = +1
                adjustment = d.yadjustment
            elif self.direction == "vertical decrease":
                delta = -1
                adjustment = d.yadjustment
            else:
                raise Exception("Unknown scroll direction: {}".format(self.direction))

            return adjustment, delta

        def get_sensitive(self):

            adjustment, delta = self.get_adjustment_and_delta()


            if adjustment is None:
                return False

            adjustment.restart_interaction_at_limit = True
            adjustment.restart_interaction_at_range = True

            if delta > 0:
                return adjustment.value < adjustment.range
            else:
                return adjustment.value > 0

        def __call__(self):

            adjustment, delta = self.get_adjustment_and_delta()

            if adjustment is None:
                raise Exception("There is no displayable with the id {}.".format(self.id))

            if self.amount == "step":
                amount = delta * adjustment.step
            elif self.amount == "page":
                amount = delta * adjustment.page
            else:
                amount = absolute.compute_raw(delta*self.amount, adjustment.range)

            if self.delay == 0.0:
                adjustment.change(adjustment.value + amount)
            else:
                adjustment.animate(amount, self.delay, self.time_warp)


    @renpy.pure
    class OpenDirectory(Action, DictEquality):
        """
        :doc: other_action
        :args: (directory)

        Opens `directory` in a file browser. `directory` is relative to
        :var:`config.basedir`.
        """

        alt = _("Open [text] directory.")

        def __init__(self, directory, absolute=False):
            import os

            if absolute:
                self.directory = directory
            else:
                self.directory = os.path.join(config.basedir, directory)

        def get_sensitive(self):
            import os

            return os.path.exists(self.directory)

        def __call__(self):
            import os
            import subprocess

            try:
                directory = renpy.fsencode(self.directory)

                if renpy.windows:
                    os.startfile(directory)
                elif renpy.macintosh:
                    subprocess.Popen([ "open", directory ])
                else:
                    subprocess.Popen([ "xdg-open", directory ])

            except Exception:
                pass

    @renpy.pure
    class CaptureFocus(Action, DictEquality):
        """
        :doc: focus_action

        If a displayable is focused when this action is run, the rectangle
        containing that displayable is stored with the name `name`. This
        rectangle can then be retrieved with the :func:`GetFocusRect` action,
        or the `focus` property of the :ref:`sl-nearrect` displayable.

        If no displayable is focused, the previous capture with that name
        is removed.

        `name`
            The name of the focus rectangle to store. This should be a string.
            The name "tooltip" is special, as it is automatically captured
            when the tooltip is changed.
        """

        def __init__(self, name="default"):
            self.name = name

        def __call__(self):
            renpy.capture_focus(self.name)
            renpy.restart_interaction()

    @renpy.pure
    class ToggleFocus(Action, DictEquality):
        """
        :doc: focus_action

        If the focus rectangle exists, clears it, otherwise captures it.

        `name`
            The name of the focus rectangle to store. This should be a string.
            The name "tooltip" is special, as it is automatically captured
            when the tooltip is changed.
        """

        def __init__(self, name="default"):
            self.name = name

        def __call__(self):
            name = self.name

            if renpy.get_focus_rect(name) is not None:
                renpy.clear_capture_focus(name)

            else:
                renpy.capture_focus(name)

            renpy.restart_interaction()

    @renpy.pure
    class ClearFocus(Action, DictEquality):
        """
        :doc: focus_action

        Clears a stored focus rectangle captured with :func:`CaptureFocus`.
        If `name` is None, all focus rectangles are cleared.
        """

        def __init__(self, name="default"):
            self.name = name

        def __call__(self):
            renpy.clear_capture_focus(self.name)
            renpy.restart_interaction()

    def GetFocusRect(name="default"):
        """
        :doc: focus_action

        If a focus rectangle with the given name has been stored (either with
        :func:`CaptureFocus`, or automatically by a tooltip, returns the
        a (x, y, h, w) rectangle. Otherwise, returns None.

        `name`
            The name of the focus rectangle to retrieve. The name "tooltip"
            is special, as it is automatically captured when the tooltip is
            changed.
        """

        return renpy.get_focus_rect(name)

    @renpy.pure
    class ExecJS(Action, DictEquality):
        """
        :doc: other_action

        Executes the given JavaScript source code. This is only supported on
        the web, and will raise an exception on other platforms. The script
        is executed asynchronously in the window context, and the return value
        is not available.

        `code`
            The JavaScript code to execute.
        """

        def __init__(self, code):
            self.code = code

        def __call__(self):
            if not renpy.emscripten:
                raise Exception("ExecJS is only supported on the web.")

            import emscripten
            emscripten.run_script(self.code)

    def CurrentScreenName():
        """
        :doc: other_screen_function

        Returns the name of the current screen, or None if there is no
        current screen. In the case of a screen including by the use
        screen, this returns the name of the screen that is doing the
        including, not the name of the screen being included.
        """

        current = renpy.current_screen()
        if current is None:
            return None

        return current.screen_name[0]

    @renpy.pure
    class CopyToClipboard(Action):
        """
        :doc: other_action

        Copies the string `s` to the system clipboard, if possible. This
        should work on desktop and mobile platforms, but will not work
        on the web.
        """

        def __init__(self, s):
            self.s = s

        def __call__(self):
            import pygame.scrap
            pygame.scrap.put(pygame.SCRAP_TEXT, self.s.encode("utf-8"))

    @renpy.pure
    class EditFile(Action):
        """
        :doc: other_action

        Requests Ren'Py to open the given file in a text editor, if possible.
        This will work on some platforms but not others.

        `filename`
            If given, the filename to open. If None, the current filename
            and line number are used, with `line` being ignored.

        `line`
            The line number to open the file at.
        """

        def __init__(self, filename=None, line=1):
            self.filename = filename
            self.line = line

        def __call__(self):

            filename = self.filename
            line = self.line

            if filename is None:
                filename, line = renpy.get_filename_line()

            try:
                renpy.launch_editor([ filename ], line)
            except Exception:
                pass

init -1500:

    transform _notify_transform:
        # These control the position.
        xalign .02 yalign .015

        # These control the actions on show and hide.
        on show:
            alpha 0
            linear .25 alpha 1.0
        on hide:
            linear .5 alpha 0.0

    screen notify:
        layer config.interface_layer
        zorder 100

        text "[message!tq]" at _notify_transform

        # This controls how long it takes between when the screen is
        # first shown, and when it begins hiding.
        timer 3.25 action Hide('notify')
