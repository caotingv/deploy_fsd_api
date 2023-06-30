from pathlib import Path
import os

# 获取当前工作目录的父目录
DEPLOY_HOME = Path.cwd().parent

# log 存放的目录
LOG_PATH = os.path.join('/var/log/deploy', '')

# 系统用户名和密码
NODE_USER = 'root'
NODE_PASS = 'Troila12#$'

# 配置文件生成路径
ETC_EXAMPLE_PATH = DEPLOY_HOME.joinpath('kly-deploy/etc_example')

# 模板存放路径
TEMPLATE_PATH = DEPLOY_HOME.joinpath('kly-deploy-api/templates')

# shell 脚本存放路径
SCRIPT_PATH = DEPLOY_HOME.joinpath('kly-deploy-api/scripts')

# 升级文件存放位置
UPGRADE_SAVE_PATH = '/opt/kly-upgrade/'

PORT = 1236
DEBUG = True

# 数据库名称
DB_NAME = DEPLOY_HOME.joinpath('kly-deploy.db')
