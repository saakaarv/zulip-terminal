from collections import defaultdict
from time import ctime
from typing import Any, Dict, List, Tuple, Union

import emoji
import urwid

from zulipterminal.ui_tools.buttons import MenuButton


class WriteBox(urwid.Pile):
    def __init__(self, view: Any) -> None:
        super(WriteBox, self).__init__(self.main_view(True))
        self.client = view.client

    def main_view(self, new: bool) -> Any:
        private_button = MenuButton(u"New Private Message")
        urwid.connect_signal(private_button, 'click', self.private_box_view)
        stream_button = MenuButton(u"New Topic")
        urwid.connect_signal(stream_button, 'click', self.stream_box_view)
        w = urwid.Columns([
            urwid.LineBox(private_button),
            urwid.LineBox(stream_button),
        ])
        if new:
            return [w]
        else:
            self.contents = [(w, self.options())]

    def private_box_view(self, button: Any=None, email: str='') -> None:
        if email == '' and button is not None:
            email = button.email
        self.to_write_box = urwid.Edit(u"To: ", edit_text=email)
        self.msg_write_box = urwid.Edit(u"> ", multiline=True)
        self.contents = [
            (urwid.LineBox(self.to_write_box), self.options()),
            (self.msg_write_box, self.options()),
        ]

    def stream_box_view(self, button: Any=None, caption: str='',
                        title: str='') -> None:
        self.to_write_box = None
        if caption == '' and button is not None:
            caption = button.caption
        self.msg_write_box = urwid.Edit(u"> ", multiline=True)
        self.stream_write_box = urwid.Edit(
            caption=u"Stream:  ",
            edit_text=caption
            )
        self.title_write_box = urwid.Edit(caption=u"Title:  ", edit_text=title)

        header_write_box = urwid.Columns([
            urwid.LineBox(self.stream_write_box),
            urwid.LineBox(self.title_write_box),
        ])
        write_box = [
            (header_write_box, self.options()),
            (self.msg_write_box, self.options()),
        ]
        self.contents = write_box

    def keypress(self, size: Tuple[int, int], key: str) -> str:
        if key == 'meta enter':
            if not self.to_write_box:
                request = {
                    'type': 'stream',
                    'to': self.stream_write_box.edit_text,
                    'subject': self.title_write_box.edit_text,
                    'content': self.msg_write_box.edit_text,
                }
                response = self.client.send_message(request)
            else:
                request = {
                    'type': 'private',
                    'to': self.to_write_box.edit_text,
                    'content': self.msg_write_box.edit_text,
                }
                response = self.client.send_message(request)
            if response['result'] == 'success':
                self.msg_write_box.edit_text = ''
        if key == 'esc':
            self.main_view(False)
        key = super(WriteBox, self).keypress(size, key)
        return key


class MessageBox(urwid.Pile):
    def __init__(self, message: Dict[str, Any], model: Any) -> None:
        self.model = model
        self.message = message
        self.caption = ''
        self.stream_id = None  # type: Union[int, None]
        self.title = ''
        self.email = ''
        super(MessageBox, self).__init__(self.main_view())

    def stream_view(self) -> Any:
        self.caption = self.message['display_recipient']
        self.stream_id = self.message['stream_id']
        self.title = self.message['subject']
        stream_title = ('header', [
            ('custom', self.caption),
            ('selected', ">"),
            ('custom', self.title)
        ])
        stream_title = urwid.Text(stream_title)
        time = urwid.Text(('custom', ctime(self.message['timestamp'])),
                          align='right')
        header = urwid.Columns([
            stream_title,
            time,
        ])
        header = urwid.AttrWrap(header, "header")
        return header

    def private_view(self) -> Any:
        self.email = self.message['sender_email']
        self.user_id = self.message['sender_id']
        self.recipients = ' ,'.join(list(
            recipient['full_name']
            for recipient in self.message['display_recipient']
        ))
        title = ('header', [
            ('custom', 'Private Message'),
            ('selected', " : "),
            ('custom', self.recipients)
            ])
        title = urwid.Text(title)
        time = urwid.Text(('custom', ctime(self.message['timestamp'])),
                          align='right')
        header = urwid.Columns([
            title,
            time,
        ])
        header = urwid.AttrWrap(header, "header")
        return header

    def reactions_view(self, reactions: List[Dict[str, Any]]) -> Any:
        if reactions == []:
            return ''
        try:
            reacts = defaultdict(int)  # type: Dict[str, int]
            custom_reacts = defaultdict(int)  # type: Dict[str, int]
            for reaction in reactions:
                if reaction['reaction_type'] == 'unicode_emoji':
                    reacts[reaction['emoji_code']] += 1
                if reaction['reaction_type'] == 'realm_emoji':
                    custom_reacts[reaction['emoji_name']] += 1
            dis = [
                '\\U' + '0'*(8-len(emoji)) + emoji + ' ' + str(reacts[emoji]) +
                ' ' for emoji in reacts]
            emojis = ''.join(e.encode().decode('unicode-escape') for e in dis)
            custom_emojis = ''.join(
                ['{} {}'.format(r, custom_reacts[r]) for r in custom_reacts])
            return urwid.Text(emoji.demojize(emojis + custom_emojis))
        except:
            return ''

    def main_view(self) -> List[Any]:
        if self.message['type'] == 'stream':
            header = self.stream_view()
        else:
            header = self.private_view()
        reactions = self.reactions_view(self.message['reactions'])
        content = [('name', self.message['sender_full_name']), "\n" +
                   self.message['content']]
        content = urwid.Text(content)
        if reactions == '':
            return [header, content]
        else:
            return [header, content, reactions]

    def selectable(self) -> bool:
        return True

    def mouse_event(self, size: Tuple[int, int], event: Any, button: Any,
                    col: int, row: int, focus: int) -> Union[bool, Any]:
        if event == 'mouse press':
            if button == 1:
                self.keypress(size, 'enter')
                return True
        return super(MessageBox, self).mouse_event(size, event, button, col,
                                                   row, focus)

    def get_recipients(self) -> str:
        emails = []
        for recipient in self.message['display_recipient']:
            email = recipient['email']
            if email == self.model.client.email:
                continue
            emails.append(recipient['email'])
        return ', '.join(emails)

    def keypress(self, size: Tuple[int, int], key: str) -> str:
        if key == 'enter':
            if self.message['type'] == 'private':
                self.model.controller.view.write_box.private_box_view(
                    email=self.get_recipients()
                    )
            if self.message['type'] == 'stream':
                self.model.controller.view.write_box.stream_box_view(
                    caption=self.message['display_recipient'],
                    title=self.message['subject']
                    )
        if key == 'c':
            if self.message['type'] == 'private':
                self.model.controller.view.write_box.private_box_view(
                    email=self.get_recipients()
                    )
            if self.message['type'] == 'stream':
                self.model.controller.view.write_box.stream_box_view(
                    caption=self.message['display_recipient']
                    )
        if key == 'S':
            if self.message['type'] == 'private':
                self.model.controller.narrow_to_user(self)
            if self.message['type'] == 'stream':
                self.model.controller.narrow_to_stream(self)
        if key == 's':
            if self.message['type'] == 'private':
                self.model.controller.narrow_to_user(self)
            if self.message['type'] == 'stream':
                self.model.controller.narrow_to_topic(self)
        if key == 'esc':
            self.model.controller.show_all_messages(self)
        if key == 'R':
            self.model.controller.view.write_box.private_box_view(
                email=self.message['sender_email']
                )
        return key
