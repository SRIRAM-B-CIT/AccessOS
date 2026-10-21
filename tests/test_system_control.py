"""
Tests for Safe System Controls and Power Confirmation
"""
from unittest.mock import patch
from accessos.settings.system_control import SystemControl, WifiNetwork


def test_volume_clamping():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/amixer"):
            # Test over 100% clamps to 100%
            SystemControl.set_volume(150)
            args = mock_run.call_args[0][0]
            assert "100%" in args

            # Test under 0% clamps to 0%
            SystemControl.set_volume(-20)
            args = mock_run.call_args[0][0]
            assert "0%" in args


def test_brightness_clamping():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        with patch("shutil.which", return_value="/usr/bin/xrandr"):
            with patch.object(SystemControl, "get_connected_display", return_value="eDP-1"):
                # Test clamping
                SystemControl.set_brightness(120)
                args = mock_run.call_args[0][0]
                assert "1.00" in args

                SystemControl.set_brightness(5)  # min 10%
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


def test_power_commands_never_use_shell():
    with patch("subprocess.Popen") as mock_popen:
        with patch("shutil.which", return_value="/bin/systemctl"):
            SystemControl.restart_system()
            # Must be called with argument list, not shell=True
            assert mock_popen.called
            call_args, call_kwargs = mock_popen.call_args
            assert isinstance(call_args[0], list)
            assert "reboot" in call_args[0]
            assert call_kwargs.get("shell") is not True
