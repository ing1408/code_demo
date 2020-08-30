#!/bin/sh
#第一步，停止apache2服务。
set -e
sudo service apache2 stop
#配置apache2ctl文件
sudo cp ./apache2ctl /usr/sbin/
sudo chmod 0755 /usr/sbin/apache2ctl
#第二步，用新的包覆盖原包（只是覆盖 不删除原包有但安装包没有的内容）
cd ./sitepackage
sudo cp -avf * /usr/lib/python3/dist-packages/
cd ../local
sudo cp -avf * /usr/lib/python3/dist-packages/openstack_dashboard/local
#第三步，收集并压缩静态包，不涉及权限（要按下面的顺序执行）
cd /usr/share/openstack-dashboard
sudo python3 manage.py collectstatic
sudo python3 manage.py compress
#第四步，配置数据库并修改权限
cd /usr/share/openstack-dashboard
sudo python3 manage.py makemigrations logs
sudo python3 manage.py makemigrations configuration
sudo python3 manage.py makemigrations operation_logs
sudo python3 manage.py migrate
sudo chown horizon /usr/lib/python3/dist-packages/openstack_dashboard
sudo chmod 0666 /usr/lib/python3/dist-packages/openstack_dashboard/lanpucloud_database
# 创建或更新数据库成功后（如果是升级且有改动是更新数据库，无改动则不会改动数据库）修改views, 添加：调用需要用数据库的接口.
cd /usr/lib/python3/dist-packages/openstack_dashboard/lpcloud_plugin/others/logs
sed -i "/# add alarm below/a\lpcloud_alarm('start', mqtt_host=settings.MQTT_HOST, mqtt_port=settings.MQTT_PORT)" views.py
#第五步，重启apache2服务
sudo service apache2 start
echo "部署完成！"
