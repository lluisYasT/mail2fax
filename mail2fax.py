#!/usr/bin/env python2
from __future__ import print_function
import mailbox
import re
import mysql.connector
#import PythonMagick

try:
    cnx = mysql.connector.connect(user='root', database='fax')

except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("Wrong username or password")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print("Database does not exist")
    else:
        print(err)


def callerid_from_email(email_address):
    cursor = cnx.cursor()
    cursor.execute(
        'SELECT number FROM fax_users WHERE email="%s"' %
        email_address)
    number = cursor.fetchone()[0]
    cursor.close()
    return number

def create_callfile(destination,callerid,email,filename):
    callfile = open("/tmp/callfile", "w")
    call = "Channel: Local/" + destination + "\@outbound-allroutes\n"
    call += "CallerID: FAX <" + str(callerid) + ">\n"
    call += "WaitTime: 60\n"
    call += "Archive: yes\n"
    call += "Context: outboundfax\n"
    call += "Extension: s\n"
    call += "Priority: 1\n"

    # FAX Options
    call += "Set: FAXFILE=" + filename + "\n"
    call += "Set: FAXHEADER=" + str(callerid) + "\n"
    call += "Set: LOCALID=" + str(callerid) + "\n"
    call += "Set: EMAIL=" + email + "\n"
    call += "Set: DESTINATION=" + destination + "\n"

    print(call)

    callfile.write(call)

    callfile.close()


if __name__ == "__main__":
    try:
        root_mailbox = mailbox.Maildir('/home/lluis/Maildir', factory=None)
        for key in root_mailbox.iterkeys():
            message = mailbox.MaildirMessage(root_mailbox[key])
            if 'S' not in message.get_flags():
                #message.set_flags('S')
                #message.set_subdir("cur")
                to = message['to']
                from_address = re.match("([^ ]+@[^ ]+\.\w+)", message['from'], flags=0)
                if not from_address:
                    continue
                print("\tTo:", to)
                print("\tFrom:", from_address.group(1))
                callerid = callerid_from_email(from_address.group(1))
                print("CallerID:", callerid)

                if not callerid:
                    print("\nUser ", from_address.group(1), " not found\n")
                    continue
                number = re.match("(\d+)", to, flags=0)
                pdf_file = None

                if not number :
                    continue
                print("\tDir: ", message.get_subdir())
                print("\tNumber: ", number.group(1))
                root_mailbox[key] = message
                root_mailbox.flush()
                print("\tFlags: ", root_mailbox[key].get_flags())
                if message.is_multipart():
                    i = 0
                    for part in message.walk():
                        if part.get_content_type()=="application/pdf":
                            pdf_file_name = part.get_filename()
                            print("\tPart filename: ", pdf_file_name)
                            print("\t\tContains a PDF file!")
                            pdf_file = part.get_payload(decode=True)
                            i += 1

                            if pdf_file:
                                f = open("/tmp/" + pdf_file_name, 'w')
                                f.write(pdf_file)
                                f.close()

                                create_callfile(number.group(1), callerid, from_address.group(1), pdf_file_name)
    finally:
        root_mailbox.close()

    cnx.close()
