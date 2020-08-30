#!/bin/sh
set -e
#停止apache2服务
sudo service apache2 stop
#备份/usr/lib/python3/dist-packages目录，以便还原至openstack原始状态。
cd /usr/lib/python3/
if [ ! -e dist-packages.tar.gz ];then
  sudo tar -czvf dist-packages.tar.gz dist-packages/
  sudo chmod 755 dist-packages.tar.gz
  else
    echo "已经备份过，无需再备份！"
fi
#备份原静态包，注：执行完成后下面两个目录下都没有static。
if [ ! -d "/var/lib/openstack-dashboard/static_backup" ];then
  sudo mv /var/lib/openstack-dashboard/static /var/lib/openstack-dashboard/static_backup
  else
    echo "已经备份过，无需再备份！"
fi
if [ -d "/var/lib/openstack-dashboard/static" ];then
   sudo rm -rf /var/lib/openstack-dashboard/static
fi
if [ ! -d "/usr/lib/python3/dist-packages/openstack_dashboard/static_backup" ];then
  sudo mv /usr/lib/python3/dist-packages/openstack_dashboard/static /usr/lib/python3/dist-packages/openstack_dashboard/static_backup
  else
    echo "已经备份过，无需再备份！"	  
fi
#备份themes目录。
if [ ! -d "/usr/lib/python3/dist-packages/openstack_dashboard/themes_backup" ];then
  sudo mv /usr/lib/python3/dist-packages/openstack_dashboard/themes /usr/lib/python3/dist-packages/openstack_dashboard/themes_backup
  else
    echo "已经备份过，无需再备份！"
fi

# 删除原有的numpy，若有的话。
if [ -d "/usr/lib/python3/dist-packages/numpy" ]; then
  sudo find /usr/lib/python3/dist-packages/ -type d -name '*numpy*' -prune -exec rm -rf {} \;
fi

#备份apache2ctl。
if [ -e "/usr/sbin/apache2ctl" ] && [ ! -e "/usr/sbin/apache2ctl_backup" ];then
  sudo mv /usr/sbin/apache2ctl /usr/sbin/apache2ctl_backup
  else
    echo "已经备份过，无需再备份！"
fi
if [ -e "/usr/sbin/apache2ctl" ];then
   sudo rm /usr/sbin/apache2ctl
fi
echo "备份完成！"
