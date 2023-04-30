# Garo Wallbox (EVSE) - HomeAssistant Integration

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

This is a custom component to allow control of Garo Wallboxes in [HomeAssistant](https://home-assistant.io).

![Example entities](https://github.com/sockless-coding/garo_wallbox/raw/master/doc/entities.png)

#### Support Development

- :coffee:&nbsp;&nbsp;[Buy the original developer a coffee](https://www.buymeacoffee.com/sockless)

## Installation

### Install using HACS

Does not work since this is an extension to another custom component.

### Install manually

Clone or copy this repository and copy the develop branch folder 'custom_components/garo_wallbox' into '<homeassistant config>/custom_components/garo_wallbox'

## Configuration

Once installed the Garo Wallbox integration can be configured via the Home Assistant integration interface
where you can enter the IP address of the device.

## Services

### Set the mode of the EVSE

Service: `garo_wallbox.set_mode`
| Parameter | Description | Example |
| - | - | - |
| entity_id | Name of the entity to change | sensor.garage_charger |
| mode | The new mode available modes: `On`, `Off`, `Schema` | On |

### Set the charge limit

Service: `garo_wallbox.set_current_limit`
| Parameter | Description | Example |
| - | - | - |
| entity_id | Name of the entity to change | sensor.garage_charger |
| limit | The new limit in Ampare | 10 |

[license-shield]: https://img.shields.io/github/license/sockless-coding/garo_wallbox.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/sockless-coding/garo_wallbox.svg?style=for-the-badge
[releases]: https://github.com/sandip1894/garo_wallbox/releases
