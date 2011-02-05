# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Alert'
        db.create_table('Alert', (
            ('alertUUID', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('alertName', self.gf('django.db.models.fields.CharField')(max_length=75)),
            ('alertText', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('alertFrequency', self.gf('django.db.models.fields.CharField')(max_length=10)),
            ('alertPrivacy', self.gf('django.db.models.fields.BooleanField')(default=True, blank=True)),
            ('sendNegativeAlert', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('lastHitDate', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('userHandling', ['Alert'])

        # Adding model 'BarMembership'
        db.create_table('BarMembership', (
            ('barMembershipUUID', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('barMembership', self.gf('django.contrib.localflavor.us.models.USStateField')(max_length=2)),
        ))
        db.send_create_signal('userHandling', ['BarMembership'])

        # Adding model 'UserProfile'
        db.create_table('UserProfile', (
            ('userProfileUUID', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], unique=True)),
            ('location', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('employer', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('avatar', self.gf('django.db.models.fields.files.ImageField')(max_length=100, blank=True)),
            ('wantsNewsletter', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('plaintextPreferred', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('activationKey', self.gf('django.db.models.fields.CharField')(max_length=40)),
            ('key_expires', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('emailConfirmed', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
        ))
        db.send_create_signal('userHandling', ['UserProfile'])

        # Adding M2M table for field barmembership on 'UserProfile'
        db.create_table('UserProfile_barmembership', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('userprofile', models.ForeignKey(orm['userHandling.userprofile'], null=False)),
            ('barmembership', models.ForeignKey(orm['userHandling.barmembership'], null=False))
        ))
        db.create_unique('UserProfile_barmembership', ['userprofile_id', 'barmembership_id'])

        # Adding M2M table for field alert on 'UserProfile'
        db.create_table('UserProfile_alert', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('userprofile', models.ForeignKey(orm['userHandling.userprofile'], null=False)),
            ('alert', models.ForeignKey(orm['userHandling.alert'], null=False))
        ))
        db.create_unique('UserProfile_alert', ['userprofile_id', 'alert_id'])


    def backwards(self, orm):
        
        # Deleting model 'Alert'
        db.delete_table('Alert')

        # Deleting model 'BarMembership'
        db.delete_table('BarMembership')

        # Deleting model 'UserProfile'
        db.delete_table('UserProfile')

        # Removing M2M table for field barmembership on 'UserProfile'
        db.delete_table('UserProfile_barmembership')

        # Removing M2M table for field alert on 'UserProfile'
        db.delete_table('UserProfile_alert')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'userHandling.alert': {
            'Meta': {'ordering': "['alertFrequency', 'alertText']", 'object_name': 'Alert', 'db_table': "'Alert'"},
            'alertFrequency': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'alertName': ('django.db.models.fields.CharField', [], {'max_length': '75'}),
            'alertPrivacy': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'blank': 'True'}),
            'alertText': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'alertUUID': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lastHitDate': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'sendNegativeAlert': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        },
        'userHandling.barmembership': {
            'Meta': {'ordering': "['barMembership']", 'object_name': 'BarMembership', 'db_table': "'BarMembership'"},
            'barMembership': ('django.contrib.localflavor.us.models.USStateField', [], {'max_length': '2'}),
            'barMembershipUUID': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'userHandling.userprofile': {
            'Meta': {'object_name': 'UserProfile', 'db_table': "'UserProfile'"},
            'activationKey': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'alert': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['userHandling.Alert']", 'null': 'True', 'blank': 'True'}),
            'avatar': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'blank': 'True'}),
            'barmembership': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'to': "orm['userHandling.BarMembership']", 'null': 'True', 'blank': 'True'}),
            'emailConfirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'employer': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'key_expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'location': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'plaintextPreferred': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'unique': 'True'}),
            'userProfileUUID': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'wantsNewsletter': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        }
    }

    complete_apps = ['userHandling']
