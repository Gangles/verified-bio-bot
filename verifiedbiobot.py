#!/usr/bin/python
# -*- coding: utf-8 -*-

import blacklist
import config
import datetime
import logging
import random
import re
import string
import sys
import time
import Levenshtein
import guess_language as lang
from twython import Twython, TwythonError

def connectTwitter():
     return Twython(config.twitter_key, config.twitter_secret,
                    config.access_token, config.access_secret)

def get_recent_tweets(twitter):
    # get the bio most recently tweeted by this bot
    timeline = twitter.get_user_timeline(screen_name = config.bot_name,
        count=200, exclude_replies=True, include_rts=False)
    recent = []
    for tweet in timeline:
        recent.append(tweet['text'])
    print(str(len(recent)) + ' recent tweets found')
    return recent

def clean_description(description):
    if not description: return ''
    words = description.split()
    link = re.compile('https?:', re.IGNORECASE)
    email = re.compile('[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}', re.IGNORECASE)
    phone = re.compile('[\d-]{4,}')
    hashtags = re.compile('[@#]')
    for i, word in enumerate(words):
        if re.search(link, word):
            words[i] = '' # remove links
        elif re.search(email, word):
            words[i] = '' # remove emails
        elif '[at]' in word or '[dot]' in word:
            words[i] = '' # remove obfuscated emails
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
        if Levenshtein.ratio(desc, bio) > 0.4:
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

    # Turkish characters
    if re.search(u'[ğüşöçİĞÜŞÖÇ]', desc): return True

    # Polish characters
    if re.search(u'[łśźżóńęąŁŚŹŻÓŃĘĄ]', desc): return True

    # Use trigrams to detect language
    if not 'en' in lang.guessLanguage(desc): return True

    return False

def get_user_bios(twitter, recent):
    result = twitter.get_friends_list(screen_name='verified',
        skip_status=True, include_user_entities=False, count=200)
    bios = []
    for user in reversed(result['users']):
        desc = clean_description(user['description'])
        if not desc or len(desc) < 30 or len(desc.split()) < 6:
            continue # enforce length
        elif user['protected'] or not user['verified']:
            continue # respect privacy
        elif blacklist.isOffensive(user['name']):
            continue # no bad words in user name
        elif blacklist.isOffensive(desc):
            continue # no bad words in description
        elif not 'en' in user['lang'] or isNotEnglish(desc):
            continue # avoid non-english
        elif isTooSimilar(desc, recent):
            continue # avoid repeating recent tweets
        elif isTooSimilar(desc, bios):
            continue # avoid repeating found bios
        else:
            bios.append(desc) # valid description
    print(str(len(bios)) + " bios to tweet")
    random.shuffle(bios)
    return bios

def postTweet(twitter, to_tweet):
    # post the given tweet
    print "Posting tweet: " + to_tweet.encode('ascii', 'ignore')
    twitter.update_status(status=to_tweet)
    return to_tweet

def timeToWait():
    # try to tweet every hour on :20
    now = datetime.datetime.now()
    wait = 60 - now.second
    wait += ((79 - now.minute) % 60) * 60
    return wait

if __name__ == "__main__":
    # heroku scheduler runs every 10 minutes
    wait = timeToWait()
    print "Wait " + str(wait) + " seconds for next tweet"
    if wait > 10 * 60:
        sys.exit(0)

    try:
        # collect bios for posting
        twitter = connectTwitter()
        recent = get_recent_tweets(twitter)
        bios = get_user_bios(twitter, recent)

        # if a new bio exists, post it
        if len(bios) > 0:
            time.sleep(min(wait, timeToWait()))
            new_tweet = postTweet(twitter, bios.pop(0))
        else:
            print 'No new bios to tweet'
        sys.exit(0)
    except SystemExit as e:
        # working as intended, exit normally
        sys.exit(e)
    except TwythonError as e:
        # error interacting with Twitter
        logging.exception("Twython Error")
        sys.exit(1)
    except:
        # some other type of error
        logging.exception(sys.exc_info()[0])
        sys.exit(1)
