import logging
import sqlite3
from flask import current_app

class UpgradeHistoryModel:
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.DB_NAME = current_app.config['DB_NAME']
        self.conn = sqlite3.connect(self.DB_NAME)

    def create_upgrade_history_table(self):
        try:
            c = self.conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS upgrade_history (
                    id INTEGER PRIMARY KEY,
                    version TEXT,
                    new_version TEXT,
                    result TEXT,
                    message TEXT,
                    endtime INTEGER
                );
            ''')
            c.close()
            self.conn.commit()
            self._logger.info("Table upgrade_history created successfully")
        except sqlite3.Error as e:
            self._logger.error(
                f"Error occurred while creating table upgrade_history: {e}")

    def add_upgrade_history(self, version, new_version, result, message, endtime):
        try:
            c = self.conn.cursor()
            c.execute('''
                INSERT INTO upgrade_history (version, new_version, result, message, endtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (version, new_version, result, message, endtime))
            c.close()
            self.conn.commit()
            self._logger.info("New upgrade_history added successfully")
        except sqlite3.Error as e:
            self._logger.error(
                f"Error occurred while adding new upgrade_history: {e}")

    def get_upgrade_history(self):
        try:
            c = self.conn.cursor()
            c.execute('''
                SELECT * FROM upgrade_history;
            ''')
            result = c.fetchone()
            c.close()
            return result
        except sqlite3.Error as e:
            self._logger.error(
                f"Error occurred while getting upgrade_history : {e}")
            return None
