#!/usr/bin/env python3
from urllib import request
import json
import os


def send_message(text):
    post = {'text': text}

    slack_url = os.getenv('HYPRSCRP_SLACK_HOOK_URL', '')
    if slack_url == '':
        print('failed to send message to slack: HYPRSCRP_SLACK_HOOK_URL not set')
        return

    try:
        json_data = json.dumps(post)
        req = request.Request('https://hooks.slack.com/services/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',
                              data=json_data.encode('ascii'),
                              headers={'Content-Type': 'application/json'})
        request.urlopen(req)
    except Exception as e:
        print('failed to send message to slack: ' + str(e))


if __name__ == '__main__':
    send_message('Hello world!')
