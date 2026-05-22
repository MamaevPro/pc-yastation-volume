"""
Управление громкостью Яндекс Станции при воспроизведении звука на ПК
-------------------------------------------------------------------
Этот скрипт отслеживает воспроизведение звука на компьютере с Windows
и автоматически изменяет громкость колонки Яндекс Станция.

Функции:
- Повышает громкость Яндекс Станции до 90%, когда начинается воспроизведение звука
- Понижает громкость Яндекс Станции до 60%, когда звук останавливается
- Управление Bluetooth ПК через вспомогательное устройство input_boolean в Home Assistant
- Автоматическое определение Яндекс Станции как устройства вывода звука
"""

import asyncio
import time
from typing import Optional

from pycaw.pycaw import AudioUtilities
import soundcard as sc
from hassapi import Hass
from winrt.windows.devices import radios


# ============================================================================
# Настройки
# ============================================================================

CONFIG = {
    "device": "media_player.yandex_station_2410789",
    "device_btpc": "input_boolean.bluetoothpc", # Вспомогательный переключатель для управления Bluetooth на ПК
    "token": "eyJhbTU",
    "hass_url": "http://192.168.1.10:8123",
    "volume_high": 0.9,      # Громкость при воспроизведении звука
    "volume_low": 0.6,       # Громкость когда звук отсутствует
    "poll_interval": 1.0,    # Секунд между проверками состояния

}

# ============================================================================
# Основные функции
# ============================================================================

def is_audio_playing() -> bool:
    """
    Проверяет, воспроизводится ли в данный момент звук на Windows.
    
    Returns:
        True если есть активные аудиосессии, иначе False.
    """
    try:
        sessions = AudioUtilities.GetAllSessions()
        return any(session.State == 1 for session in sessions)
    except Exception as e:
        print(f"Ошибка проверки состояния звука: {e}")
        return False


def get_default_audio_device_name() -> Optional[str]:
    """
    Получает имя текущего устройства вывода звука по умолчанию.
    
    Returns:
        Имя устройства или None при ошибке.
    """
    try:
        return sc.default_speaker().name
    except Exception as e:
        print(f"Ошибка получения имени устройства вывода звука: {e}")
        return None


async def set_bluetooth_power(turn_on: bool) -> None:
    """
    Включает или выключает Bluetooth на Windows.
    
    Args:
        turn_on: True для включения Bluetooth, False для выключения.
    """
    try:
        all_radios = await radios.Radio.get_radios_async()
        target_state = radios.RadioState.ON if turn_on else radios.RadioState.OFF
        
        for radio in all_radios:
            if radio.kind == radios.RadioKind.BLUETOOTH:
                print(f"Радио Bluetooth: {radio.name}")
                print(f"Текущее состояние: {radio.state}")
                await radio.set_state_async(target_state)
                print(f"Bluetooth {'ВКЛЮЧЕН' if turn_on else 'ВЫКЛЮЧЕН'}")
                return
        print("Радио Bluetooth не найдено")
    except Exception as e:
        print(f"Ошибка управления Bluetooth: {e}")


def on_bluetooth_state_change(event: dict) -> None:
    """
    Callback для отслеживания изменений input_boolean в Home Assistant.
    
    Args:
        event: Событие изменения состояния Home Assistant.
    """
    try:
        new_state = event["data"]["new_state"]["state"]
        if new_state == "on":
            asyncio.run(set_bluetooth_power(True))
        elif new_state == "off":
            asyncio.run(set_bluetooth_power(False))
    except Exception as e:
        print(f"Ошибка обработки состояния Bluetooth: {e}")


def set_yandex_station_volume(volume_level: float) -> None:
    """
    Устанавливает громкость колонки Яндекс Станция через Home Assistant.
    
    Args:
        volume_level: Значение от 0.0 до 1.0.
    """
    try:
        hass.call_service(
            "volume_set",
            entity_id=CONFIG["device"],
            volume_level=volume_level
        )
        print(f"Громкость установлена на {volume_level * 100:.0f}%")
    except Exception as e:
        print(f"Ошибка установки громкости: {e}")


# ============================================================================
# Основной цикл
# ============================================================================

if __name__ == "__main__":
    # Подключение к Home Assistant
    hass = Hass(
        hassurl=CONFIG["hass_url"],
        token=CONFIG["token"],
        verify=False,      # Отключить проверку SSL для самоподписанных сертификатов
        timeout=3,         # Таймаут запроса в секундах
    )
    
    # Подписка на изменение состояния Bluetooth переключателя
    hass.subscribe_to_state_changes(
        on_bluetooth_state_change,
        entity_id=CONFIG['device_btpc']
    )
    
    # Основной цикл мониторинга
    prev_state = is_audio_playing()
    print(f"Начальное состояние звука: {'воспроизводится' if prev_state else 'остановлен'}")
    
    while True:
        time.sleep(CONFIG["poll_interval"])
        
        # Получение текущего устройства вывода
        device_name = get_default_audio_device_name()
        if not device_name:
            continue
        
        # Проверяем, что устройство вывода - Яндекс Станция
        if "Yandex.Station" not in device_name:
            continue
        
        # Получение текущего состояния воспроизведения
        current_state = is_audio_playing()
        
        # Обработка изменений состояния
        if not prev_state and current_state:
            print("Началось воспроизведение звука - повышаем громкость")
            set_yandex_station_volume(CONFIG["volume_high"])
            
        elif prev_state and not current_state:
            print("Воспроизведение остановлено - понижаем громкость")
            set_yandex_station_volume(CONFIG["volume_low"])
        
        prev_state = current_state
