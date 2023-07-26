#!/usr/bin/bash
#set -x

upgrade_path=$1

deploy_path=/root/deploy
deploy_etc_example_path=${deploy_path}/kly-deploy/etc_example
upgrade_etc_example_path=${upgrade_path}/kly-deploy/etc_example
upgrade_ansible_path=${upgrade_path}/kly-deploy/ansible
ceph_ansible_path=${deploy_path}/kly-deploy/ceph-ansible


# 检测参数
function check_param() {
  if  [[ ! -n "$upgrade_path" ]]; then
    echo "缺少必要参数，例如: bash upgrade.sh [upgrade_path, /opt/upgrade_resource_v2.1.0]"
    exit 1
  fi
}

# Deployment Scripts upgrade
function deploy_scripts_upgrade() {
  now_data=`date +%s`
  mv ${deploy_path}/kly-deploy ${deploy_path}/kly-deploy_${now_data}
  cp -r ${upgrade_path}/kly-deploy ${deploy_path}/

  \cp -rf ${deploy_path}/kly-deploy_${now_data}/etc_example ${deploy_path}/kly-deploy/
  \cp -rf ${upgrade_path}/kly-deploy/etc_example/upgrade-globals.yaml ${deploy_path}/kly-deploy/etc_example/
}

# Service upgrade
function deploy_upgrade_program() { 
  # backup database
  mariadb_root_password=$(grep 'mariadb_root_password:' ${deploy_etc_example_path}/global_vars.yaml | awk '{print $2}')
  docker exec mariadb mysqldump -uroot -p${mariadb_root_password} --all-databases --single-transaction > ${upgrade_path}/database-backup-`date +%Y-%m-%d-%H-%M`.sql
  if [ $? -eq 0 ]; then
    process "backup_data" "" true 1 "backup_data"
  else
    process "backup_data" "数据库备份失败" false 1 "backup_data"
    exit 1
  fi

  # service_upgrade
  ansible-playbook -i ${deploy_etc_example_path}/hosts -e @${deploy_etc_example_path}/ceph-globals.yaml -e @${deploy_etc_example_path}/global_vars.yaml -e @${upgrade_etc_example_path}/upgrade-globals.yaml ${upgrade_ansible_path}/95-upgrade.yaml> /var/log/deploy/upgrade.log 2>&1
  if [ "$(grep 'failed=' /var/log/deploy/upgrade.log | awk '{print $6}' | awk -F '=' '{print $2}' | awk '$1 != 0')" = "" ] ; then
    process "deploy_upgrade_program" "" true 2 "deploy_upgrade_program"
  else
    process "deploy_upgrade_program" "执行升级程序失败" false 2 "deploy_upgrade_program"
    exit 1
  fi

  check_service_port
  ports=(9000 9001 9002 9003 9010 9090 9093)
  for port in "${ports[@]}"
  do
    if ! netstat -an | grep -w "$port" >/dev/null
    then
      process "check_service_status" "Port $port is not in use" false 3 "check_service_status"
      exit 1
    fi
  done
  process "check_service_status" "" true 3 "check_service_status"
  deploy_scripts_upgrade
  exit 0
}

# 上报所有流程
function all_process() {
  sqlite3 /root/deploy/kly-deploy.db <<EOF
    DELETE FROM upgrade_process_status;
    DELETE FROM upgrade_now_status;
    INSERT INTO upgrade_process_status(en, message, result, sort, zh) VALUES ("unzip_upgrade_package", "", "true", 0, "解压升级包");
    INSERT INTO upgrade_process_status(en, message, result, sort, zh) VALUES ("backup_data", "", "true", 1, "备份数据库");
    INSERT INTO upgrade_process_status(en, message, result, sort, zh) VALUES ("deploy_upgrade_program", "", "true", 2, "执行升级程序");
    INSERT INTO upgrade_process_status(en, message, result, sort, zh) VALUES ("check_service_status", "", "true", 3, "检测环境状态");
EOF
}

# 上报中间流程
function process() {
  echo "('$1', '$2', '$3', $4, '$5')"
  sqlite3 /root/deploy/kly-deploy.db "INSERT INTO upgrade_now_status(en, message, result, sort, zh) VALUES ('$1', '$2', '$3', $4, '$5');"
}

check_param
deploy_upgrade_program
