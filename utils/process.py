import ctypes
import psutil
from utils.logger import Logger


class ProcessThreadManager:
    """进程和线程管理工具类"""
    
    def __init__(self):
        self.suspended_thread_ids = []
        self.kernel32 = ctypes.windll.kernel32
        self.logger = Logger()

    def find_process_by_name(self, process_name):
        """
        通过进程名称查找进程
        参数:
            process_name: 进程名称
        返回:
            进程ID，如果未找到则返回None
        """
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == process_name:
                self.logger.info(f"找到目标进程: {proc.info['name']} (PID: {proc.info['pid']})")
                return proc.info['pid']
        self.logger.error(f"未找到 {process_name} 进程")
        return None

    def get_most_active_thread(self, pid):
        """
        获取指定进程中最活跃的线程
        参数:
            pid: 进程ID
        返回:
            最活跃的线程信息，如果失败则返回None
        """
        try:
            process = psutil.Process(pid)
            threads = process.threads()
            if not threads:
                self.logger.error("未找到任何线程")
                return None
            return max(threads, key=lambda t: t.system_time + t.user_time)
        except Exception as e:
            self.logger.error(f"获取活跃线程时发生错误: {e}")
            return None

    def suspend_thread(self, thread_id):
        """
        挂起指定线程
        参数:
            thread_id: 线程ID
        返回:
            是否成功挂起
        """
        thread_handle = self.kernel32.OpenThread(0x0002, False, thread_id)
        if not thread_handle:
            self.logger.error(f"无法打开线程 ID {thread_id}")
            return False

        try:
            if self.kernel32.SuspendThread(thread_handle) != 0xFFFFFFFF:
                self.logger.info(f"已挂起线程 ID: {thread_id}")
                if thread_id not in self.suspended_thread_ids:
                    self.suspended_thread_ids.append(thread_id)
                return True
            self.logger.error(f"无法挂起线程 ID {thread_id}")
            return False
        finally:
            self.kernel32.CloseHandle(thread_handle)

    def resume_thread(self, thread_id):
        """
        恢复指定线程
        参数:
            thread_id: 线程ID
        返回:
            是否成功恢复
        """
        thread_handle = self.kernel32.OpenThread(0x0002, False, thread_id)
        if not thread_handle:
            self.logger.error(f"无法打开线程 ID {thread_id}")
            return False

        try:
            if self.kernel32.ResumeThread(thread_handle) != 0xFFFFFFFF:
                self.logger.info(f"已恢复线程 ID: {thread_id}")
                if thread_id in self.suspended_thread_ids:
                    self.suspended_thread_ids.remove(thread_id)
                return True
            self.logger.error(f"无法恢复线程 ID {thread_id}")
            return False
        finally:
            self.kernel32.CloseHandle(thread_handle)

    def get_suspended_threads(self):
        """
        获取当前已挂起的线程列表
        返回:
            已挂起的线程ID列表的副本
        """
        return self.suspended_thread_ids.copy()

    def resume_all_suspended_threads(self):
        """
        恢复所有已挂起的线程
        返回:
            成功恢复的线程ID列表
        """
        resumed_threads = []
        for thread_id in self.get_suspended_threads():
            if self.resume_thread(thread_id):
                resumed_threads.append(thread_id)
        return resumed_threads

    def kill_process_by_pid(self, pid):
        """
        根据进程ID终止进程
        参数:
            pid: 进程ID
        返回:
            bool: 是否成功终止进程
        """
        try:
            process = psutil.Process(pid)
            process_name = process.name()
            process.kill()
            self.logger.info(f"已成功终止进程 {process_name} (PID: {pid})")
            return True
        except psutil.NoSuchProcess:
            self.logger.error(f"未找到 PID 为 {pid} 的进程")
        except psutil.AccessDenied:
            self.logger.error(f"没有权限终止 PID 为 {pid} 的进程")
        except Exception as e:
            self.logger.error(f"终止进程时发生错误: {e}")
        return False

    def kill_process_by_name(self, process_name):
        """
        根据进程名称终止所有匹配的进程
        参数:
            process_name: 进程名称
        返回:
            list: 成功终止的进程ID列表
        """
        killed_pids = []
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == process_name:
                    pid = proc.info['pid']
                    try:
                        proc.kill()
                        killed_pids.append(pid)
                        self.logger.info(f"已终止进程 {process_name} (PID: {pid})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        self.logger.error(f"终止进程 {process_name} (PID: {pid}) 失败: {e}")
            
            if not killed_pids:
                self.logger.error(f"未找到名为 {process_name} 的进程")
            else:
                self.logger.info(f"共终止了 {len(killed_pids)} 个 {process_name} 进程")
            
            return killed_pids
        except Exception as e:
            self.logger.error(f"终止进程时发生错误: {e}")
            return killed_pids

    def kill_process_safely(self, pid=None, process_name=None):
        """
        安全地终止进程，会先尝试正常终止，如果失败则强制终止
        参数:
            pid: 进程ID（可选）
            process_name: 进程名称（可选）
        返回:
            list: 成功终止的进程ID列表
        """
        killed_pids = []
        
        try:
            if pid:
                process = psutil.Process(pid)
                self._terminate_process_safely(process)
                killed_pids.append(pid)
            elif process_name:
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.info['name'] == process_name:
                        if self._terminate_process_safely(proc):
                            killed_pids.append(proc.info['pid'])
            
            return killed_pids
        except Exception as e:
            self.logger.error(f"终止进程时发生错误: {e}")
            return killed_pids

    def _terminate_process_safely(self, process):
        """
        内部方法：安全地终止单个进程
        """
        try:
            pid = process.pid
            process_name = process.name()
            
            # 首先尝试正常终止
            process.terminate()
            try:
                process.wait(timeout=3)  # 等待进程终止，最多3秒
                self.logger.info(f"已正常终止进程 {process_name} (PID: {pid})")
                return True
            except psutil.TimeoutExpired:
                # 如果正常终止失败，则强制终止
                process.kill()
                self.logger.info(f"已强制终止进程 {process_name} (PID: {pid})")
                return True
                
        except psutil.NoSuchProcess:
            self.logger.error(f"进程已不存在 (PID: {pid})")
        except psutil.AccessDenied:
            self.logger.error(f"没有权限终止进程 (PID: {pid})")
        except Exception as e:
            self.logger.error(f"终止进程时发生错误: {e}")
        return False


