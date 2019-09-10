from dotenv import load_dotenv
from twython import Twython, TwythonError
import json
import os
import os.path
import pandas as pd
import sys
import time
import tweepy

#############################################################################################
# configure environment with .env
#############################################################################################
load_dotenv()

CONSUMER_KEY = os.environ['CONSUMER_KEY']
CONSUMER_SECRET = os.environ['CONSUMER_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_TOKEN_SECRET = os.environ['ACCESS_TOKEN_SECRET']
TWEET_STORAGE_PATH = os.environ['TWEET_STORAGE_PATH']
LOOKUP_RESULTS = os.environ['LOOKUP_RESULTS']
ENRICHR_URL = os.environ.get('ENRICHR_URL', 'https://amp.pharm.mssm.edu/Enrichr')

#############################################################################################
# collect tweets
#############################################################################################
#  need to schedule the launch of the 'main' function on a server at specified time intervals.

def collect_tweets(user_name,path):
  print('Checking for new tweets...')
  #
  # authentication
  twitter = Twython(CONSUMER_KEY, CONSUMER_SECRET, oauth_version=2)
  access_token = twitter.obtain_access_token()
  twitter = Twython(CONSUMER_KEY, access_token=access_token)
  #
  # Ensure path exists
  if not os.path.exists(path):
    os.mkdir(path)
  #
  # discover the id of the latest collected tweet 
  onlyfiles = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
  onlyfiles = sorted(onlyfiles, key=lambda x:float(x.split('.json')[0][0:]), reverse=True)
  #
  # collect tweets from the Timeline of 
  if len(onlyfiles)==0:
    try: # get the latest tweet
      user_timeline = twitter.get_user_timeline(screen_name= user_name, count=1, exclude_replies=True, include_rts=False)
    except TwythonError as e:
      print(e)
  else:
    with open(path + onlyfiles[0], 'r') as f: # reat json of the latest tweet
      datastore = json.load(f)
    #
    tweet_id = datastore['id_str'] # the latest json tweet
    try:
      user_timeline = twitter.get_user_timeline(screen_name= user_name, count=200, exclude_replies=True, include_rts=False, since_id = str(tweet_id))
    except TwythonError as e:
      print(e)
  #  
  # save data to json files (each tweet has a file)
  for i in range(0,len(user_timeline)):
    ts =str(time.mktime(time.strptime(user_timeline[i]['created_at'],"%a %b %d %H:%M:%S +0000 %Y"))) # convert to epoch time
    with open(path + ts +'.json', 'w', encoding='utf8') as file: # file name is post creation time (epoch time)
      json.dump(user_timeline[i],file, indent=2)

#############################################################################################
# Automaticaly reply to a tweet of GWASbot
#############################################################################################

# Call the function with: (a) Status text + a link to the photo/ data from Enrichr, and (b) ID of the original tweet.

def reply_to_GWA(reply_to_user, text, media, tweet_id):
  #
  # authentication
  message = '@' + reply_to_user + " " + text
  print('Tweeting reply to {}: {} with media {}...'.format(tweet_id, message, media))
  auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
  auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
  api = tweepy.API(auth)
  #
  media_uploads = [api.media_upload(medium) for medium in media]
  media_ids = [upload.media_id_string for upload in media_uploads]
  api.update_status(
    message,
    str(tweet_id),
    media_ids=media_ids,
  ) # post a reply

#############################################################################################
# Main
#############################################################################################

def main(dry_run=False):
  # Collect tweets from GWASbot's Timeline
  collect_tweets('SbotGwa', TWEET_STORAGE_PATH)
  # Get the latest tweet
  print('Getting latest tweet metadata...')
  latest_file = sorted(os.listdir(TWEET_STORAGE_PATH))[-1]
  latest_json = json.load(open(os.path.join(TWEET_STORAGE_PATH, latest_file), 'r'))
  # Resolve the identifier from the description (first line, s/ /_/g)
  identifier = latest_json['text'].splitlines()[0].replace(' ','_').lower().strip()
  print('Searching for identifier: {}...'.format(identifier))
  # Look up the identifier in the results
  df = pd.read_csv(LOOKUP_RESULTS, sep='\t')
  matches = df[df['identifier'].map(lambda s, q=identifier: q in s.lower().strip())]
  print(matches.shape[0])
  if matches.shape[0] == 0:
    raise Exception("{} not found".format(identifier))
  if matches.shape[0] > 1:
    raise Exception("{} matched multiple results".format(identifier))
  print('Preparing reply...')
  # Post link as reply
  enrichr_link = matches['enrichr'].iloc[0]
  desc = '{}. Enrichr link: {} @MaayanLab #Enrichr #Bioinformatics #BD2K #LINCS @BD2KLINCSDCIC @DruggableGenome #BigData'.format(
    identifier.replace('_', ' ').capitalize(), enrichr_link,
  )
  # Get the screenshot file relative to the results file
  screenshot = [os.path.join(
    os.path.dirname(LOOKUP_RESULTS),
    matches['screenshot'].iloc[0]
  )]
  # Get the tweet id for which to reply to
  tweet_id = latest_json['id_str']
  if dry_run:
    print('reply_to_GWA("SbotGwa", {}, {}, {}, '.format(desc, screenshot, tweet_id))
  else:
    reply_to_GWA(
      'SbotGwa',
      desc,
      screenshot,
      tweet_id,
    )

if __name__ == '__main__':
  main(dry_run='--dry-run' in sys.argv)
