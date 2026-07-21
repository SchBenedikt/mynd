from datetime import datetime

from core.scheduler import AutomationEngine

automation_engine = AutomationEngine({})

def _init_automation_engine():
    from app.agent_loop import WEB_TOOL_MAP
    global automation_engine
    automation_engine = AutomationEngine(WEB_TOOL_MAP)


def _start_indexing_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        sched = BackgroundScheduler()

        @sched.scheduled_job('interval', minutes=30, id='email_index', max_instances=1)
        def auto_index_emails():
            try:
                from data.plugins.email import _list_accounts, email_search
                for acct in _list_accounts():
                    try:
                        email_search(query="ALL", max_results=10, account=acct)
                    except Exception:
                        pass
            except Exception:
                pass

        @sched.scheduled_job('interval', minutes=60, id='nc_index', max_instances=1)
        def auto_index_nextcloud():
            try:
                from data.plugins.nextcloud import nextcloud_caldav_query, nextcloud_tasks_query
                today = datetime.now().strftime("%Y%m%d")
                nextcloud_caldav_query(today, today)
                nextcloud_tasks_query()
            except Exception:
                pass

        @sched.scheduled_job('cron', hour=7, minute=0, id='morning_briefing', max_instances=1)
        def auto_briefing():
            try:
                import requests
                requests.get("http://127.0.0.1:5001/api/agent/briefing", timeout=30)
            except Exception:
                pass

        sched.start()
    except Exception:
        pass
