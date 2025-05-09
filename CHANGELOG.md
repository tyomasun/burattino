# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## 2024-03-27
### Added
- Ability to close position by strategy singnal (SignalType.CLOSE = 2). 

## 2023-08-20
### Fixed
- Calculation available money on account was changed. Now, calculation method consider short positions.
- A few stability changes

## 2023-08-12
### Fixed
- Market stream reconnect was added due feedback and the following comment in the python SDK [Issue](https://github.com/Tinkoff/invest-python/issues/210#issuecomment-1482780561)

## 2022-07-22
### Removed
- Backtesting code has been moved to
[invest-tool](https://github.com/EIDiamond/invest-tools/tree/main/backtesting/tinkoff_historic_candles_py) project. 
- Removed working mode from configuration. 
Now, the bot project only for trading purposes. 
All other tools will be in repo [projects](https://github.com/EIDiamond).   

## 2022-06-16
### Changed
- Trade logic and telegram api are working asynchronously. 
The main reason was telegram api is working pretty long, sometimes more than a few seconds.
After all changes telegram messages don't block trade logic.
- Changed dependencies: 
  - Removed 'python-telegram-bot'
  - Added 'aiogram' 
