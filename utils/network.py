from scapy.arch.windows import get_windows_if_list
import subprocess
import traceback

class NetworkInterface:
    def __init__(self, logger):
        """
        初始化网络接口管理器
        @param logger: Logger实例
        """
        self.logger = logger
        
        # 创建通用的 startupinfo 对象
        self.startupinfo = subprocess.STARTUPINFO()
        self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.startupinfo.wShowWindow = subprocess.SW_HIDE

    def _is_valid_ip(self, ip):
        """检查是否为有效的普通IP地址"""
        try:
            # 排除特殊IP地址
            if not ip or ':' in ip:  # 排除IPv6
                return False
            
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            
            # 检查每个部分是否为0-255的数字
            if not all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
                return False
            
            # 排除特殊IP地址范围
            if (
                ip.startswith('0.') or      # 0.0.0.0/8
                ip.startswith('127.') or    # 127.0.0.0/8 (本地回环)
                ip.startswith('169.254.') or # 169.254.0.0/16 (链路本地)
                ip.startswith('224.') or    # 224.0.0.0/4 (组播地址)
                ip.startswith('240.') or    # 240.0.0.0/4 (保留地址)
                ip == '255.255.255.255'     # 广播地址
            ):
                return False
            
            return True
        except:
            return False

    def load_interfaces(self):
        """加载网络接口列表"""
        try:
            # 获取 scapy 的接口列表
            scapy_interfaces = get_windows_if_list()
            
            active_interfaces = []
            inactive_interfaces = []
            default_interface = None

            for iface in scapy_interfaces:
                # 跳过没有IP地址的接口
                if not iface.get('ips'):
                    continue
                    
                # 获取接口基本信息
                name = iface.get('name', '')
                desc = iface.get('description', '')
                
                # 跳过虚拟接口
                if any(keyword in desc.lower() 
                      for keyword in ['loopback', 'vmware', 'virtualbox', 'hyper-v', 'bluetooth']):
                    continue
                
                # 获取有效的IPv4地址
                ipv4_addr = next((ip for ip in iface.get('ips', []) if self._is_valid_ip(ip)), None)
                is_active = bool(ipv4_addr)
                is_vpn = any(vpn_keyword in desc.lower() for vpn_keyword in ['vpn', 'virtual', '虚拟'])
                
                # 构建显示名称
                display_desc = desc[:47] + '...' if len(desc) > 50 else desc
                display_name = f"{name} [{'已连接' if is_active else '未连接'}] - {display_desc}"

                # 处理接口状态
                if is_active:
                    active_interfaces.append(display_name)
                    # 设置默认接口（优先选择以太网）
                    if not default_interface and not is_vpn and (
                        "ethernet" in desc.lower() or "以太网" in desc.lower()
                    ):
                        default_interface = display_name
                else:
                    inactive_interfaces.append(display_name)

                # 记录接口信息
                self.logger.info(
                    f"\n   接口: {name}\n"
                    f"   描述: {desc}\n"
                    f"   类型: {'VPN/虚拟' if is_vpn else '物理'}\n"
                    f"   状态: {'已连接' if is_active else '未连接'}\n"
                    f"   IP地址: {ipv4_addr or '无'}\n"
                    f"   MAC地址: {iface.get('mac', '')}"
                )

            return {
                'interfaces': active_interfaces + inactive_interfaces,
                'default': default_interface,
                'active_count': len(active_interfaces)
            }
            
        except Exception as e:
            self.logger.error(f"加载网络接口失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {'interfaces': [], 'default': None, 'active_count': 0}
