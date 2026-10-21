"""
Tests for Safe System Controls, Wi-Fi Security, and Permission Failure Handling
"""
from unittest.mock import patch, MagicMock
from accessos.settings.system_control import SystemControl, WifiNetwork


def test_volume_clamping():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/amixer"):
            # Test over 100% clamps to 100%
            ok, msg = SystemControl.set_volume(150)
            assert ok is True
            args = mock_run.call_args[0][0]
            assert "100%" in args

            # Test under 0% clamps to 0%
            ok, msg = SystemControl.set_volume(-20)
            assert ok is True
            args = mock_run.call_args[0][0]
            assert "0%" in args


def test_brightness_clamping():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/xrandr"):
            with patch.object(SystemControl, "get_connected_display", return_value="eDP-1"):
                # Test clamping
                ok, msg = SystemControl.set_brightness(120)
                assert ok is True
                args = mock_run.call_args[0][0]
                assert "1.00" in args

                ok, msg = SystemControl.set_brightness(5)  # min 10%
                assert ok is True
                args = mock_run.call_args[0][0]
                assert "0.10" in args


def test_wifi_list_parsing():
    raw_output = (
        "HomeWiFi:85:WPA2:*\n"
        "OfficeGuest:60:WPA2: \n"
        "PublicOpen:40:Open: \n"
        ":0:: \n"  # empty SSID ignored
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = raw_output
        with patch("shutil.which", return_value="/usr/bin/nmcli"):
            nets = SystemControl.list_wifi_networks()
            assert len(nets) == 3
            assert nets[0].ssid == "HomeWiFi"
            assert nets[0].signal == 85
            assert nets[0].in_use is True
            assert nets[1].ssid == "OfficeGuest"
            assert nets[1].in_use is False
            assert nets[2].security == "Open"


def test_wifi_password_never_in_argv():
    secret_pass = "SuperSecretPassword123!"
    with patch("subprocess.Popen") as mock_popen:
        proc_mock = MagicMock()
        proc_mock.communicate.return_value = ("Connected", "")
        proc_mock.returncode = 0
        mock_popen.return_value = proc_mock
        with patch("shutil.which", return_value="/usr/bin/nmcli"):
            ok, msg = SystemControl.connect_wifi("ProtectedSSID", password=secret_pass)
            assert ok is True

            # Verify Popen was called
            assert mock_popen.called
            call_args = mock_popen.call_args[0][0]

            # 1. Password must NEVER be in command line argument list
            for arg in call_args:
                assert secret_pass not in arg, f"Password leaked into argv: {arg}"

            # 2. Must use --ask flag
            assert "--ask" in call_args

            # 3. Password must be piped strictly via communicate input
            input_sent = proc_mock.communicate.call_args[1].get("input", "")
            assert secret_pass in input_sent


def test_power_commands_never_use_shell():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        with patch("shutil.which", return_value="/bin/systemctl"):
            ok, msg = SystemControl.restart_system()
            assert ok is True
            assert mock_run.called
            call_args, call_kwargs = mock_run.call_args
            assert isinstance(call_args[0], list)
            assert "reboot" in call_args[0]
            assert call_kwargs.get("shell") is not True


def test_permission_denied_fails_safely():
    with patch("subprocess.run") as mock_run:
        # Simulate Polkit permission denied
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Interactive authentication required."
        with patch("shutil.which", return_value="/bin/systemctl"):
            ok, msg = SystemControl.restart_system()
            assert ok is False
            assert "Restart failed" in msg

            ok, msg = SystemControl.poweroff_system()
            assert ok is False
            assert "Power off failed" in msg
