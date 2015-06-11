#!/usr/bin/env python2
import mailbox
import re


try:
    root_mailbox = mailbox.Maildir('/home/lluis/Maildir', factory=None)
    for key in root_mailbox.iterkeys():
        message = mailbox.MaildirMessage(root_mailbox[key])
        if 'S' not in message.get_flags():
            #message.set_flags('S')
            #message.set_subdir("cur")
            pdf_file = None
            to = message['to']
            from_address = message['from']
            number = re.match("^(\d+)", to, flags=0)
            if 1==1 :
                print "\tTo: ", to
                print "\tFrom: ", from_address
                print "\tDir: ", message.get_subdir()
                #print "\tNumber: ", number.group(1)
                root_mailbox[key] = message
                root_mailbox.flush()
                print "\tFlags: ", root_mailbox[key].get_flags()
                if message.is_multipart():
                    i = 0
                    for part in message.walk():
                        if part.get_content_type()=="application/pdf":
                            pdf_file_name = part.get_filename()
                            print "\tPart filename: ", pdf_file_name
                            print "\t\tContains a PDF file!"
                            pdf_file = part.get_payload(decode=True)
                            i += 1

                            if pdf_file:
                                f = open("/tmp/" + pdf_file_name, 'w')
                                f.write(pdf_file)
                                f.close()
finally:
    root_mailbox.close()

