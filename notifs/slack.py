#!/usr/bin/env python3
from urllib import request
import json
import os


def _send(slack_url: str, text: str) -> None:
    post = {'text': text}

    try:
        json_data = json.dumps(post)
        req = request.Request(slack_url,
                              data=json_data.encode('ascii'),
                              headers={'Content-Type': 'application/json'})
        request.urlopen(req)
    except Exception as e:
        print('failed to send message to slack: {}'.format(str(e)))


def send_health_message(text: str) -> None:
    slack_url = os.getenv('HYPRSCRP_HEALTH_SLACK_HOOK_URL', '')
    if slack_url == '':
        print('failed to send message to slack: HYPRSCRP_HEALTH_SLACK_HOOK_URL not set')
        return

    _send(slack_url, text)


def send_message(text) -> None:
    slack_url = os.getenv('HYPRSCRP_SLACK_HOOK_URL', '')
    if slack_url == '':
        print('failed to send message to slack: HYPRSCRP_SLACK_HOOK_URL not set')
        return

    _send(slack_url, text)


if __name__ == '__main__':
    send_health_message('Hello health!')
    send_message('Hello world!')
