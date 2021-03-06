from django.db import models
from django.contrib.auth.models import User
from swingtime.models import Event
from datetime import timedelta
from keyedcache import NotCachedError, cache_get, cache_set, cache_key
import logging
log = logging.getLogger(__file__)

MODERATION_CHOICES = (
	('U', 'UnModerated'),
	('A', 'Accepted'),
	('R', 'Rejected'),
)


class Year(models.Model):
    year = models.CharField(max_length=4)
    location = models.CharField(max_length=50)
    participants = models.IntegerField(null=True, blank=True)
    theme = models.CharField(max_length=20, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    event_start = models.DateField(null=True)
    event_end = models.DateField(null=True)

    class Meta:
        ordering = ('year',)

    def __unicode__(self):
        return self.year

    def daterange(self):
      """
      Returns a list of datetime objects for every day of the event
      """
      if self.event_start and self.event_end:
          numdays = (self.event_end - self.event_start).days + 1
          return [self.event_start + timedelta(days=x) for x in range(0,numdays)]
      else:
          return []



class CircularStreet(models.Model):
    year = models.ForeignKey(Year)
    name = models.CharField(max_length=50)
    order = models.IntegerField(null=True, blank=True)
    distance_from_center = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ('year','order',)

    def __unicode__(self):
        return self.year.year + ":" + self.name


class TimeStreet(models.Model):
    year = models.ForeignKey(Year)
    hour = models.IntegerField() # Should be restricted
    minute = models.IntegerField() # Should be restricted
    name = models.CharField(max_length=5)

    class Meta:
        ordering = ('year','name',)

    def __unicode__(self):
        return self.year.year + ":" + self.name


class ThemeCampManager(models.Manager):
    """Manager which filters out list_online=False"""

    def get_query_set(self):
        return super(ThemeCampManager, self).get_query_set().filter(list_online=True)

    def get_and_cache(self, **kwargs):
        key = cache_key('ThemeCamp', 'all', **kwargs)
        log.debug('key = %s', key)
        try:
            results = cache_get(key)
            log.debug('got all camps from cache')
        except NotCachedError:
            log.debug('getting camps from db')
            if kwargs:
                results = self.filter(**kwargs)
            else:
                results = self.all()

            results = list(results)
            cache_set(key, value=results, length=60*60*24) # set for one day

        return results

class ThemeCampAllManager(models.Manager):
    """Manager which does not filter out list_online=False"""

    def get_and_cache(self, **kwargs):
        key = cache_key('ThemeCampAll', 'all', **kwargs)
        log.debug('key = %s', key)
        try:
            results = cache_get(key)
            log.debug('got all camps from cache')
        except NotCachedError:
            log.debug('getting camps from db')
            if kwargs:
                results = self.filter(**kwargs)
            else:
                results = self.all()

            results = list(results)
            cache_set(key, value=results, length=60*60*24) # set for one day

        return results

class ThemeCamp(models.Model):
    name = models.CharField(max_length=100)
    year = models.ForeignKey(Year)
    slug = models.SlugField(max_length=255, null=True,blank=True)
    description = models.TextField(null=True,blank=True)
    url = models.URLField(null=True,blank=True)
    contact_email = models.EmailField(null=True,blank=True)
    hometown = models.CharField(max_length=50, null=True, blank=True)
    image = models.ImageField(upload_to='theme_camp', null=True, blank=True)
    location_string = models.CharField(max_length=250, null=True, blank=True)
    list_online = models.NullBooleanField(null=False, blank=False, default=True)
    circular_street = models.ForeignKey(CircularStreet, null=True, blank=True)
    time_address = models.TimeField(null=True, blank=True)
    bm_fm_id = models.IntegerField(null=True,blank=True)
    deleted = models.NullBooleanField(null=True, blank=True, default=False)

    # make the default "objects" return just public results
    all_objects = ThemeCampAllManager()
    objects = ThemeCampManager()

    class Meta:
        ordering = ('year','name',)

    def __unicode__(self):
        return self.year.year + ":" + self.name

    @models.permalink
    def get_absolute_url(self):
        return ('playaevents.views.themecampid', (), {
            'theme_camp_id':self.id,
            'year_year':self.year.year,
        })

class ArtInstallation(models.Model):
    year = models.ForeignKey(Year)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, null=True, blank=True)
    artist = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    image = models.ImageField(upload_to='art_install', null=True, blank=True)
    circular_street = models.ForeignKey(CircularStreet, null=True, blank=True)
    time_address = models.TimeField(null=True, blank=True)
    distance = models.IntegerField(null=True, blank=True)
    location_string = models.CharField(max_length=50, null=True, blank=True)
    bm_fm_id = models.IntegerField(null=True,blank=True)

    class Meta:
        ordering = ('year','name',)

    def __unicode__(self):
        return self.year.year + ":" + self.name

    @models.permalink
    def get_absolute_url(self):
        return ('playaevents.views.art_installation_id', (), {
            'art_installation_id':self.id,
            'year_year':self.year.year,
        })

class PlayaEventManager(models.Manager):
    def get_and_cache(self, **kwargs):
        key = cache_key('PlayaEvent', 'all', **kwargs)
        try:
            results = cache_get(key)
            log.debug('got all events from cache')
        except NotCachedError:
            log.debug('getting events from db')
            if kwargs:
                results = self.filter(**kwargs)
            else:
                results = self.all()

            results = list(results)
            cache_set(key, value=results, length=60*60*24) # set for one day

        return results

    def search(self, searchtext, year=None):
        """Performs a full-text search on PlayaEvent and Event, returning the queryset."""

        if year and year != 'all':
            sql = "select pe.* from playaevents_playaevent pe inner join swingtime_event se on (se.id = pe.event_ptr_id) inner join playaevents_year y on (pe.year_id = y.id) where (se.search_tsv @@ plainto_tsquery(%s) or pe.search_tsv @@ plainto_tsquery(%s)) and y.year=%s and pe.moderation='A' and pe.list_online='t'"
            params = (searchtext, searchtext, year)
        else:
            sql = "select pe.* from playaevents_playaevent pe inner join swingtime_event se on (se.id = pe.event_ptr_id) where (se.search_tsv @@ plainto_tsquery(%s) or pe.search_tsv @@ plainto_tsquery(%s)) and pe.moderation='A' and pe.list_online='t'"
            params = (searchtext, searchtext)

        log.debug('search sql=%s, params=%s', sql, params)
        return self.raw(sql, params=params)


class PlayaEvent(Event):
  year = models.ForeignKey(Year)
  print_description = models.CharField(max_length=150, null=False, blank=True)
  slug = models.SlugField(max_length=255)
  hosted_by_camp = models.ForeignKey(ThemeCamp, null=True, blank=True)
  located_at_art = models.ForeignKey(ArtInstallation, null=True, blank=True)
  other_location = models.CharField(max_length=255, null=True, blank=True)
  check_location = models.NullBooleanField()
  url = models.URLField(null=True, blank=True)
  contact_email = models.EmailField(null=True, blank=True)
  all_day = models.NullBooleanField()
  list_online = models.NullBooleanField()
  list_contact_online = models.NullBooleanField()
  creator = models.ForeignKey(User, null=False)
  moderation =  models.CharField(max_length=1, choices=MODERATION_CHOICES, default='U')
  speaker_series = models.NullBooleanField(default=False)
  password_hint = models.CharField(max_length=120, blank=True, null=True)
  password = models.CharField(max_length=40, blank=True, null=True)

  objects = PlayaEventManager()

  def __unicode__(self):
    return self.year.year + ":" + self.title

  @models.permalink
  def get_absolute_url(self):
      return ('playaevents.views.playa_event_view', (), {
          'playa_event_id':self.id,
          'year_year':self.year.year,
      })
