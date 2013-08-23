#!/usr/bin/env python

import models
from datetime import datetime, timedelta
from google.appengine.api import urlfetch
from xml.etree import ElementTree # XML parsing

def update_feeds():
    active_feeds = {}
    for r in models.Reading.all():
        if not active_feeds.has_key(r.feed):
            active_feeds[r.feed] = []
        active_feeds[r.feed].append(r.user)
    for fid in active_feeds.keys():
        feed = models.Feed.get_by_id(fid)
        result = urlfetch.fetch(feed.url)
        if result.status_code != 200:
            raise Exception("Failed to fetch feed URL: " + feed.url)
        root = ElementTree.fromstring(result.content)
        atom_ns = '{http://www.w3.org/2005/Atom}'
        if root.tag == "rss":
            new_articles = parse_rss(root)
        elif root.tag == atom_ns+"feed":
            new_articles = parse_atom(root, atom_ns)
        else:
            print "Error: unknown feed format (must be RSS or Atom)"
            return

        for article in new_articles:
            match = models.Article.get_by_properties({"title":article["title"], "url":article["url"]})
            if not match:
                a = models.Article(title = article["title"], url = article["url"], content = article["content"], date = article["date"], feed = feed.key().id())
                a.put()
                for user in active_feeds[fid]:
                    u = models.Unread(user = user, article = a.key().id())
                    u.put()

def parse_rss(root):
  new_articles = []
  for article in root.find("channel").findall("item"):
      title = article.find("title").text
      url = article.find("link").text
      content = article.find("description").text

      # parse pubDate
      # date is given as "Mon, 12 Aug 2013 01:00:00 GMT" or "-0000" instead of "GMT"
      pubDate = article.find("pubDate")
      if pubDate != None:
        pubDate = pubDate.text
        try:
          date = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
        except Exception as e:
          try:
            offset = int(pubDate[-5:])
            date = datetime.strptime(pubDate[:-6], "%a, %d %b %Y %H:%M:%S")
            delta = timedelta(hours = offset / 100)
            date -= delta
          except Exception as e:
            try:
              date = datetime.strptime(pubDate[:16], "%a, %d %b %Y")
            except Exception as e:
              date = datetime.now()
      else:
        date = datetime.now()
      new_articles.append({"title":title, "url":url, "content":content, "date":date})
  return new_articles

def parse_atom(root, namespace):
  new_articles = []
  for article in root.findall(namespace+"entry"):
      title = article.find(namespace+"title").text
      url = article.find(namespace+"link").get("href")
      content = article.find(namespace+"content").text if article.find(namespace+"content") is not None else article.find(namespace+"summary").text

      # parse pubDate (<updated>)
      # date is given as "2013-08-12T01:00:00Z" or "-01:00" instead of "Z" and may optionally have two decimals of extra precision in the seconds place
      pubDate = article.find(namespace+"updated")
      if pubDate != None:
        pubDate = pubDate.text
        try:
          # so I'm not trying very hard here, just ignoring the timezone
          date = datetime.strptime(pubDate[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception as e:
          try:
            date = datetime.strptime(pubDate[:10], "%Y-%m-%d")
          except Exception as e:
            date = datetime.now()
      else:
        date = datetime.now()
      new_articles.append({"title":title, "url":url, "content":content, "date":date})
  return new_articles

if __name__ == "__main__":
    update_feeds()
