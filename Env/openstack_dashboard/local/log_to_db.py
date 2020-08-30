# coding:utf-8
"""
Created on 2020年05月27日
@author: Wayne Created for LPCloud alarm handler
"""

# usage example: SendAlarm('handle', source='lpcloud_handle_update',content='abc')
# add in database tables: log_data, op_log_combined

from django.utils.translation import ugettext_lazy as _
import threading
import queue
import random
import string
from openstack_dashboard import settings as dashboard_settings
from django.utils import timezone
import logging

# add db tables below
from openstack_dashboard.lpcloud_plugin.others.logs.models import log_data
from openstack_dashboard.lpcloud_plugin.log_management.operation_logs.models import op_log_combined

logger = logging.getLogger(__name__)
semaphore = threading.Semaphore(0)


# decorator
def singleton(cls):
    def _singleton(*args, **kwargs):
        return cls.action(cls, *args, **kwargs)
    return _singleton


def get_content(**kwargs):
    content = ''
    if 'content' in kwargs.keys():
        content = kwargs['content']
    return content


# add on 0804 for op_log_combined
def get_subject_name(**kwargs):
    subject_name = ''
    if 'subject_name' in kwargs.keys():
        subject_name = kwargs['subject_name']
    return subject_name


def get_level(**kwargs):
    level = 'debug'
    level_list = ['error', 'warning', 'info', 'debug']
    if 'level' in kwargs.keys():
        if kwargs['level'] in level_list:
            level = kwargs['level']
        else:
            level = 'debug'
    return level


def get_subject_id(**kwargs):
    subject_id = ''
    if 'subject_id' in kwargs.keys():
        subject_id = kwargs['subject_id']
    return subject_id


def get_message(**kwargs):
    message = ''
    if 'message' in kwargs.keys():
        message = kwargs['message']
    return message


@singleton
class SendAlarm(object):
    db_thread = None
    handle_queue = queue.Queue()

    # edit incoming msg translation here, todo read from a py file instead of this.
    trans_source_dict = {'lpcloud_center': _('lpcloud_center')}
    trans_content_dict = {'Connect to Nascloud fail': _('Connect to Nascloud fail')}

    # default max record of op logs
    op_log_max = 20000
    try:
        op_log_max = dashboard_settings.op_log_max
    except Exception as error:
        logger.warning('get openstack log max from settings fail, reason is %s' % error)

    # op_log_keys = ['subject', 'subject_name', 'subject_id', 'subject_action', 'message']

    def action(self, *args, **kwargs):
        logger.debug('entry')
        # handle conditions where no need to start thread first.
        if len(args) != 1 or (args[0] != 'add' and args[0] != 'delete' and args[0] != 'exit' and args[0] != 'handle'):
            logger.warning('wrong parameters.')

        elif args[0] == 'exit':
            self.stop_thread(self)

        elif args[0] == 'add' and (
                ('content' not in kwargs.keys() or 'source' not in kwargs.keys())
                and
                (
                        'subject' not in kwargs.keys() or
                        (
                                'subject_id' not in kwargs.keys() and 'subject_name' not in kwargs.keys()
                        )
                        or 'subject_action' not in kwargs.keys()
                )
        ):
            logger.warning('source is required for adding data but not provided. Pass.')

        elif 'alarm_id' not in kwargs.keys() and args[0] == 'delete':
            logger.warning('alarm_id is required for deleting data but not provided. Pass.')

        elif args[0] == 'handle' and ('content' not in kwargs.keys() or 'source' not in kwargs.keys()):
            logger.warning('source and content are required for marking alarm handled but not provided. Pass.')

        else:
            if self.db_thread:
                pass
            else:
                self.db_thread = self.HandleAlarm(1, 'handle alarm thread', self.handle_queue, self.op_log_max)

                try:
                    self.db_thread.start()
                except (RuntimeError, Exception) as error:
                    logger.warning('start handle alarm thread fail! Reason is %s.' % error)
                    return

            # edit untranslated source, content
            try:
                if kwargs['source'] in self.trans_source_dict:
                    kwargs['source'] = self.trans_source_dict[kwargs['source']]

                if kwargs['content'] in self.trans_content_dict:
                    kwargs['content'] = self.trans_content_dict[kwargs['content']]
            except (KeyError, ValueError) as error:
                logger.warning('get source and content from report fail. Reason is %s' % error)

            if args[0] == 'add':
                self.add_data(self, **kwargs)
            elif args[0] == 'delete':
                self.delete_data(self, **kwargs)
            elif args[0] == 'handle':
                self.handle_data(self, **kwargs)
            elif args[0] == 'exit':
                self.stop_thread(self)
            else:
                logger.warning('Unsupported action on send_alarm.')

    def add_data(self, **kwargs):
        logger.debug('add entry')

        if 'subject' not in kwargs.keys():
            alarm_id = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(16))

            new_action = {'action_type': 'add', 'alarm_data': {'alarm_id': alarm_id,
                                                               'source': kwargs['source'],
                                                               'level': get_level(self, **kwargs),
                                                               'content': get_content(self, **kwargs)
                                                               }
                          }

            self.handle_queue.put(new_action)
            logger.debug('add request put in queue. Alarm id is: %s' % alarm_id)
            semaphore.release()
        else:
            # add log op_log_combined
            stored_record = 0
            current_record = op_log_combined.objects.all().count()
            count_file = '/usr/lib/python3/dist-packages/openstack_dashboard/local/logs_count.py'

            try:
                with open(count_file, 'r') as f:
                    logger.warning('reading')
                    stored_number = f.read()

                if len(stored_number) != 0:
                    stored_record = int(stored_number)

            except Exception as error:
                logger.warning("Can not read count file. Reason is %s" % error)
            else:
                logger.warning('read count file completed.')

            # test
            # logger.warning('get stored record is %s' % stored_record)
            # test end

            if stored_record > current_record:
                current_record = stored_record
                logger.warning('stored record bigger than current record from op log table.')

            new_action = {'action_type': 'add',
                          'alarm_data': {'action_id': str(current_record + 1), 'subject': kwargs['subject'],
                                         'subject_id': get_subject_id(self, **kwargs),
                                         'subject_action': kwargs['subject_action'],
                                         'subject_name': get_subject_name(self, **kwargs),
                                         'message': get_message(self, **kwargs)
                                         }
                          }

            self.handle_queue.put(new_action)
            logger.debug('add request put in queue. Log id is: %s' % str(current_record + 1))

            # write to file
            try:
                with open(count_file, 'w') as file_to_write:
                    file_to_write.write(str(current_record + 1))
            except (FileNotFoundError, PermissionError) as error:
                logger.error('write to local count file fail, reason is: %s' % error)

            semaphore.release()
        return

    def delete_data(self, **kwargs):
        logger.debug('delete entry')
        new_action = {'action_type': 'delete', 'alarm_data': {'alarm_id': kwargs['alarm_id']}}

        self.handle_queue.put(new_action)
        logger.debug('delete request put in queue. Alarm id is: %s' % kwargs['alarm_id'])
        semaphore.release()
        return

    def handle_data(self, **kwargs):
        logger.debug('handle entry')
        new_action = {'action_type': 'handle', 'alarm_data': {'source': kwargs['source'], 'content': kwargs['content']}}

        self.handle_queue.put(new_action)
        logger.debug('mark handle request put in queue. content is: %s' % kwargs['content'])
        semaphore.release()
        return

    # to stop publish thread
    def stop_thread(self):
        logger.debug('entry')

        if self.db_thread:
            self.db_thread.exit_thread()
            semaphore.release()
        else:
            logger.warning('thread not started, no need to stop.')

        return

    # thread modify data in database   +++++++++++++++++++++++++++++++++++++++++
    class HandleAlarm(threading.Thread):
        initiate = True

        def __init__(self, threadID, name, handle_queue, op_log_max):
            threading.Thread.__init__(self)
            self.threadID = threadID
            self.name = name
            self.handle_queue = handle_queue
            self.op_log_max = op_log_max
            self.__action_type = ''
            self.__alarm_data = {}
            self.__log_data = {}
            self.__exit_flag = False

        def run(self):
            while not self.__exit_flag:
                logger.debug('run new round')
                semaphore.acquire()
                self.modify_db()
            print('exit HandleAlarm thread.')

        def exit_thread(self):
            self.__exit_flag = True
            pass

        def modify_db(self):

            logger.debug('entry')
            logger.debug('there are %s request(s) in queue.' % str(self.handle_queue.qsize()))

            if self.handle_queue.qsize() > 0:
                report_temp = self.handle_queue.get()
                try:
                    self.__action_type = report_temp['action_type']
                    self.__alarm_data = report_temp['alarm_data']
                except (KeyError, ValueError) as error:
                    logger.warning('can not get data correctly from queue, reason is %s' % error)
                    return
                else:
                    if self.__action_type == 'add':
                        self.__handle_add_data()

                    elif self.__action_type == 'delete':
                        self.__handle_delete_data()
                    elif self.__action_type == 'handle':
                        self.__handle_handle_data()
                    else:
                        logger.warning('unsupported action type.')
            else:
                logger.warning('report empty')

            return

        def __handle_add_data(self):
            logger.debug('entry')

            # for op_log_combined, share same self.__alarm_data = {}
            if 'subject' in self.__alarm_data.keys():
                # 1 Check max record
                current_op_set = op_log_combined.objects.all()

                if current_op_set.count() >= self.op_log_max:
                    try:
                        op_log_combined.objects.order_by('date_created').first().delete()
                    except Exception as error:
                        logger.warning(
                            'operation record exceeds openstack max log number! '
                            'Fail to delete the oldest record. Reason is: %s' % error
                        )
                    else:
                        logger.warning(
                            'operation record exceeds openstack max log number! Delete the oldest record success.')
                # 2 Action
                try:
                    add_data = op_log_combined(action_id=self.__alarm_data['action_id'],
                                               subject=self.__alarm_data['subject'],
                                               subject_id=self.__alarm_data['subject_id'],
                                               subject_action=self.__alarm_data['subject_action'],
                                               subject_name=self.__alarm_data['subject_name'],
                                               message=self.__alarm_data['message']
                                               )
                    add_data.save()
                except Exception as error:
                    logger.warning('add action log in database fail, reason is %s' % error)
            else:
                # 1 Check max record
                current_set = log_data.objects.all()

                if current_set.count() >= 10000:
                    try:
                        log_data.objects.order_by('date_created').first().delete()
                    except Exception as error:
                        logger.warning(
                            'alarm record exceeds 10000! Fail to delete the oldest record. Reason is: %s' % error)
                    else:
                        logger.warning('alarm record exceeds 10000! Delete the oldest record success.')
                # 2 Action

                # Conditions adding new record:
                # same content not found in table
                # or, same content found but latest one is handled
                # This is to avoid adding exact same content in the table.
                content_add = self.__alarm_data['content']
                source_add = self.__alarm_data['source']

                # edit on 0720, to trans level
                level_add = _(self.__alarm_data['level'])
                # edit ends

                check_set = log_data.objects.filter(source=source_add, content=content_add).order_by('-date_created')
                # check_time_condition = (datetime.now(tz=timezone.utc)-check_set.first().date_created).seconds > 10

                if len(check_set) == 0 or check_set.first().is_handled == True:
                    try:
                        add_data = log_data(alarm_id=self.__alarm_data['alarm_id'], source=source_add,
                                            content=content_add, level=level_add, date_handled=None)
                        add_data.save()

                    except Exception as error:
                        logger.warning('add record in database fail, reason is: %s' % error)
                        return
                    else:
                        logger.debug('add record in database success.')
                        return
                else:
                    logger.warning('receive duplicate add request, not handling this.')

        def __handle_delete_data(self):
            logger.debug('entry')
            try:
                log_data.objects.filter(alarm_id=self.__alarm_data['alarm_id']).delete()

            except Exception as error:
                logger.warning('delete record in database fail, reason is: %s' % error)
                return
            else:
                logger.debug('delete record in database success.')
                return

        def __handle_handle_data(self):
            logger.debug('entry')
            try:
                log_data.objects.filter(source=self.__alarm_data['source'],
                                        content=self.__alarm_data['content'],
                                        is_handled=False
                                        ).update(is_handled=True, date_handled=timezone.now())

            except Exception as error:
                logger.warning('mark alarm handled in database fail, reason is: %s' % error)
                return
            else:
                logger.debug('mark alarm handled in database success.')
                return
