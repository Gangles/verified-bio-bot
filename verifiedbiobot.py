#!/usr/bin/python

import blacklist
import config
import datetime
import re
import string
import sys
import time
import Levenshtein
from twython import Twython

def connectTwitter():
     return Twython(config.twitter_key, config.twitter_secret,
                    config.access_token, config.access_secret)

def get_last_tweet(twitter):
    # get the bio most recently tweeted by this bot
    timeline = twitter.get_user_timeline(screen_name = config.bot_name)
    if len(timeline) > 0:
        return timeline[0]['text']
    else:
        return None

def clean_description(description):
    words = description.split()
    link = re.compile('https?:', re.IGNORECASE)
    email = re.compile('[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}', re.IGNORECASE)
    phone = re.compile('[\d-]{7,}')
    hashtags = re.compile('[@#]')
    for i, word in enumerate(words):
        if re.search(link, word):
            words[i] = '' # remove links
        elif re.search(email, word):
            words[i] = '' # remove emails
        elif re.search(phone, word):
            words[i] = '' # remove phone numbers
        else:
            # remove hashtags and @-mentions
            words[i] = hashtags.sub('', word)
    words = filter(None, words)
    new_desc = string.join(words, ' ')
    if (len(new_desc) > 140):
        new_desc = new_desc[:137] + '...'
    return new_desc

def isTooSimilar(desc, bios):
    for bio in bios:
        if Levenshtein.ratio(desc, bio) > 0.5:
            return True
    return False

def isNotEnglish(desc):
    # Cyrillic characters
    if re.search(u'[\u0400-\u04FF]', desc): return True

    # Japanese characters
    if re.search(u'[\u3040-\u309F]', desc): return True
    if re.search(u'[\u30A0-\u30FF]', desc): return True
    if re.search(u'[\uFF00-\uFF9F]', desc): return True
    if re.search(u'[\u4E00-\u9FAF]', desc): return True

    # Chinese characters
    if re.search(u'[\u4E00-\u9FFF]', desc): return True
    if re.search(u'[\u3400-\u4DFF]', desc): return True
    if re.search(u'[\uF900-\uFAFF]', desc): return True

    # Korean characters
    if re.search(u'[\uAC00-\uD7AF]', desc): return True

    # Arabic characters
    if re.search(u'[\u0600-\u06FF]', desc): return True

    return False

def get_user_bios(twitter, most_recent):
    result = twitter.get_friends_list(screen_name='verified', skip_status=True,
                                        include_user_entities=False, count=200)
    bios = []
    found_last = not most_recent
    for user in reversed(result['users']):
        desc = clean_description(user['description'])
        if not found_last and most_recent in desc:
            found_last = True
        elif found_last:
            if user['protected'] or not user['verified']:
                continue # respect privacy
            elif blacklist.isOffensive(user['name']):
                continue # no bad words in user name
            elif blacklist.isOffensive(desc):
                continue # no bad words in description
            elif not 'en' in user['lang'] or isNotEnglish(desc):
                continue # avoid non-english
            elif isTooSimilar(desc, bios):
                continue # avoid repeating
            elif len(desc) > 20:
                bios.append(desc)

    if found_last:
        # new bios that haven't been tweeted
        print(str(len(bios)) + " new bios found")
        return bios
    elif most_recent:
        # most recent bio isn't in the results
        return get_user_bios(twitter, None)
    else:
        # can't find a new bio
        return bios

def postTweet(twitter, to_tweet):
    # post the given tweet
    twitter.update_status(status=to_tweet)
    print "Posted tweet: " + to_tweet.encode('ascii', 'ignore')
    return to_tweet

def waitToTweet():
    # try to tweet every :20 & :50
    now = datetime.datetime.now()
    wait = 60 - now.second
    if now.minute < 20:
        wait += (20 - now.minute) * 60
    elif now.minute < 50:
        wait += (50 - now.minute) * 60
    else:
        wait += (80 - now.minute) * 60
    print "Wait " + str(wait) + " seconds for next tweet"
    time.sleep(wait)

if __name__ == "__main__":
    # setup
    twitter = connectTwitter()
    most_recent = get_last_tweet(twitter)
    bios = []

    # main loop
    while True:
        try:
            waitToTweet()
            if len(bios) == 0:
                bios = get_user_bios(twitter, most_recent)
            if len(bios) > 0:
                most_recent = postTweet(twitter, bios.pop(0))
            else:
                print 'No new bios to tweet'
        except:
            print "Error:", sys.exc_info()[0]
        time.sleep(10)
