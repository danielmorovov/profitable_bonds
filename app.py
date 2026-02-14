import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime, timezone, timedelta
from io import StringIO

# Configure page
st.set_page_config(page_title="MOEX Bonds Analysis",
                   page_icon="📊",
                   layout="wide",
                   initial_sidebar_state="expanded")


@st.cache_data(ttl=1800)  # Кешируем на 30 минут
def get_cbr_key_rate():
    """Получает текущую ключевую ставку ЦБ РФ через API"""
    try:
        import xml.etree.ElementTree as ET
        from datetime import datetime, timedelta
        import re

        # Формируем диапазон дат (последние 30 дней для получения актуальной ставки)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=30)

        # SOAP запрос для получения ключевой ставки
        url = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <KeyRateXML xmlns="http://web.cbr.ru/">
      <fromDate>{from_date.strftime('%Y-%m-%d')}T00:00:00</fromDate>
      <ToDate>{to_date.strftime('%Y-%m-%d')}T00:00:00</ToDate>
    </KeyRateXML>
  </soap:Body>
</soap:Envelope>"""

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '"http://web.cbr.ru/KeyRateXML"'
        }

        response = requests.post(url,
                                 data=soap_body,
                                 headers=headers,
                                 timeout=15)
        response.raise_for_status()

        # Парсим XML ответ
        root = ET.fromstring(response.text)

        # Ищем данные о ключевой ставке в ответе
        rates = []

        # Ищем в XML элементах
        for elem in root.iter():
            if elem.text and elem.text.strip():
                text = elem.text.strip()
                try:
                    val = float(text)
                    if 1.0 <= val <= 50.0:  # Разумный диапазон для ключевой ставки
                        rates.append(val)
                except ValueError:
                    pass

            # Проверяем атрибуты
            for attr_name, attr_value in elem.attrib.items():
                try:
                    val = float(attr_value)
                    if 1.0 <= val <= 50.0:
                        rates.append(val)
                except ValueError:
                    pass

        # Также попробуем найти ставки через регулярные выражения в тексте
        text_content = response.text

        # Паттерны для поиска ставки в тексте
        rate_patterns = [
            r'>(\d{1,2}(?:\.\d{1,2})?)<',  # Числа между тегами
            r'(\d{1,2}(?:\.\d{1,2})?)%',  # Числа с процентами
            r'Rate[^>]*>(\d{1,2}(?:\.\d{1,2})?)',  # Rate теги
            r'value[^>]*>(\d{1,2}(?:\.\d{1,2})?)'  # Value теги
        ]

        for pattern in rate_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                try:
                    val = float(match)
                    if 1.0 <= val <= 50.0:
                        rates.append(val)
                except ValueError:
                    continue

        if rates:
            # Берем первую найденную ставку (самую актуальную, так как API возвращает данные в обратном хронологическом порядке)
            current_rate = rates[0]
            return float(current_rate)
        else:
            # Попробуем альтернативный источник - страницу ЦБ РФ
            try:
                page_response = requests.get(
                    "https://www.cbr.ru/hd_base/KeyRate/", timeout=10)
                if page_response.status_code == 200:
                    # Ищем ставку на странице
                    page_text = page_response.text
                    rate_match = re.search(r'(\d{1,2}(?:\.\d{1,2})?)\s*%',
                                           page_text)
                    if rate_match:
                        alt_rate = float(rate_match.group(1))
                        if 1.0 <= alt_rate <= 50.0:
                            return alt_rate
            except:
                pass

            return 0.0

    except Exception as e:
        return 0.0


@st.cache_data(ttl=3600)  # Кешируем на 1 час
def get_cbr_exchange_rates():
    """Получает курсы валют ЦБ РФ"""
    try:
        response = requests.get('https://www.cbr-xml-daily.ru/daily_json.js',
                                timeout=10)
        response.raise_for_status()
        data = response.json()

        rates = {
            'USD': data['Valute']['USD']['Value'],
            'EUR': data['Valute']['EUR']['Value'],
            'CNY': data['Valute']['CNY']['Value']
        }
        return rates
    except Exception as e:
        st.warning(f"Не удалось получить курсы валют: {e}")
        # Возвращаем примерные значения в случае ошибки
        return {'USD': 79.5, 'EUR': 92.8, 'CNY': 11.0}


def get_moex_bonds_data():
    """Получает данные об облигациях с MOEX ISS API и возвращает DataFrame"""
    url = "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.xml"

    try:
        # Делаем запрос к API с увеличенным таймаутом
        try:
            response = requests.get(url, timeout=90)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            # Повторная попытка с еще большим таймаутом
            response = requests.get(url, timeout=120)
            response.raise_for_status()

        # Читаем XML и преобразуем в DataFrame
        xml_string = StringIO(response.text)
        df = pd.read_xml(xml_string,
                         xpath=".//data[@id='securities']/rows/row")

        # Получаем дополнительные данные из другого блока (marketdata)
        xml_string = StringIO(response.text)
        marketdata_df = pd.read_xml(xml_string,
                                    xpath=".//data[@id='marketdata']/rows/row")

        # Проверяем наличие колонки для объединения
        merge_column = None
        possible_merge_columns = ['secid', 'SECID', 'security_id', 'id']

        for col in possible_merge_columns:
            if col in df.columns and col in marketdata_df.columns:
                merge_column = col
                break

        if merge_column:
            # Объединяем данные
            merged_df = pd.merge(df,
                                 marketdata_df,
                                 on=merge_column,
                                 how='inner')
            return merged_df
        else:
            # Если не найдена общая колонка, возвращаем только securities data
            st.warning(
                "Не найдена общая колонка для объединения данных. Используются только данные securities."
            )
            return df

    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка сети при получении данных: {e}")
        return None
    except Exception as e:
        st.error(f"Ошибка при обработке данных: {e}")
        return None


def process_bonds_data(df,
                       coupon_min=25,
                       coupon_max=35,
                       lot_max=1500,
                       min_coupon=0.0):
    """Обрабатывает данные об облигациях согласно требованиям"""
    try:
        # Проверяем наличие необходимых колонок
        required_columns = [
            'SHORTNAME', 'COUPONPERIOD', 'COUPONVALUE', 'LOTVALUE',
            'PREVPRICE', 'NEXTCOUPON', 'FACEUNIT'
        ]
        missing_columns = [
            col for col in required_columns if col not in df.columns
        ]

        if missing_columns:
            st.error(
                f"Отсутствуют необходимые колонки в данных: {missing_columns}")
            return None

        # Выбираем нужные колонки
        result_df = df[required_columns].copy()

        # Преобразуем валюту: SUR -> RUB
        result_df['FACEUNIT'] = result_df['FACEUNIT'].replace('SUR', 'RUB')

        # Преобразуем типы данных
        result_df['COUPONPERIOD'] = pd.to_numeric(result_df['COUPONPERIOD'],
                                                  errors='coerce')
        result_df['COUPONVALUE'] = pd.to_numeric(result_df['COUPONVALUE'],
                                                 errors='coerce')
        result_df['LOTVALUE'] = pd.to_numeric(result_df['LOTVALUE'],
                                              errors='coerce')
        result_df['PREVPRICE'] = pd.to_numeric(result_df['PREVPRICE'],
                                               errors='coerce')

        # Удаляем строки с пропущенными значениями
        result_df = result_df.dropna()

        if result_df.empty:
            st.warning("Нет данных после фильтрации пропущенных значений")
            return None

        # Фильтруем по COUPONPERIOD
        filtered_df = result_df[(result_df['COUPONPERIOD'] >= coupon_min) & (
            result_df['COUPONPERIOD'] <= coupon_max)].copy()

        # Фильтруем по LOTVALUE
        filtered_df = filtered_df[filtered_df['LOTVALUE'] <= lot_max]

        # Фильтруем по минимальному купону
        filtered_df = filtered_df[filtered_df['COUPONVALUE'] >= min_coupon]

        if filtered_df.empty:
            st.warning(
                f"Нет облигаций, соответствующих критериям: купонный период {coupon_min}-{coupon_max} дней, номинал ≤{lot_max} у.е."
            )
            return None

        # Рассчитываем коэффициент Q (защита от деления на ноль)
        filtered_df = filtered_df[filtered_df['COUPONVALUE'] > 0].copy()
        filtered_df['Q'] = (
            (filtered_df['LOTVALUE'] * filtered_df['PREVPRICE']) /
            filtered_df['COUPONVALUE']) / 100

        # Рассчитываем годовую доходность после налогов
        # DEBIT = 10000 * (COUPONVALUE * (365 / COUPONPERIOD) * 0.87) / (PREVPRICE * LOTVALUE)
        filtered_df['ANNUAL_YIELD'] = 10000 * (
            filtered_df['COUPONVALUE'] * (365 / filtered_df['COUPONPERIOD']) *
            0.87) / (filtered_df['PREVPRICE'] * filtered_df['LOTVALUE'])

        # Сортируем по возрастанию Q (меньшее Q = больше потенциальный доход)
        sorted_df = filtered_df.sort_values('ANNUAL_YIELD', ascending=False)

        # Возвращаем результат без индекса
        return sorted_df.reset_index(drop=True)

    except Exception as e:
        st.error(f"Ошибка при обработке данных: {e}")
        return None


def format_dataframe_for_display(df, key_rate):
    """Форматирует DataFrame для отображения с переименованными колонками и цветовым индикатором"""
    if df is None or df.empty:
        return None

    display_df = df.copy()

    # Добавляем цветовой индикатор
    def get_risk_category(yield_val):
        # Используем небольшую дельту для включения пограничных значений из-за точности float
        epsilon = 1e-9
        if yield_val < key_rate - epsilon:
            return "🔴 Невыгодно"
        elif key_rate - epsilon <= yield_val <= 30 + epsilon:
            return "🟢 Норма"
        else:
            return "🟠 Риск"

    display_df['RISK_CATEGORY'] = display_df['ANNUAL_YIELD'].apply(
        get_risk_category)

    # Переименовываем колонки для лучшего отображения
    column_mapping = {
        'RISK_CATEGORY': 'Категория',
        'SHORTNAME': 'Название облигации',
        'COUPONPERIOD': 'Купонный период (дни)',
        'COUPONVALUE': 'Купон (у.е.)',
        'LOTVALUE': 'Номинал (у.е.)',
        'PREVPRICE': 'Цена (%)',
        'Q': 'Коэффициент Q',
        'ANNUAL_YIELD': 'Годовая доходность (%)',
        'NEXTCOUPON': 'Дата следующего купона',
        'FACEUNIT': 'Валюта'
    }

    display_df = display_df.rename(columns=column_mapping)

    # Переорганизуем колонки - категория последняя
    cols = [col for col in display_df.columns if col != 'Категория'
            ] + ['Категория']
    display_df = display_df[cols]

    # Форматируем числовые колонки
    for col in display_df.columns:
        if col in ['Купон (у.е.)', 'Номинал (у.е.)']:
            # Форматируем с удалением лишних нулей
            display_df[col] = display_df[col].apply(
                lambda x: f"{x:.2f}".rstrip('0').rstrip('.'))
        elif col in ['Коэффициент Q', 'Годовая доходность (%)']:
            display_df[col] = display_df[col].round(2)
        elif col == 'Цена (%)':
            display_df[col] = display_df[col].round(3)

    return display_df


def main():
    # Заголовок приложения
    st.title("📊 Анализ облигаций MOEX")
    st.markdown("---")

    # Sidebar с параметрами фильтрации
    st.sidebar.header("⚙️ Параметры фильтрации")

    # Параметры фильтрации
    coupon_min = st.sidebar.slider(
        "Минимальный купонный период (дни)",
        min_value=1,
        max_value=365,
        value=25,
        help="Минимальное количество дней в купонном периоде")

    coupon_max = st.sidebar.slider(
        "Максимальный купонный период (дни)",
        min_value=coupon_min,
        max_value=365,
        value=35,
        help="Максимальное количество дней в купонном периоде")

    lot_max = st.sidebar.number_input(
        "Максимальный номинал (у.е.)",
        min_value=100,
        max_value=10000,
        value=1500,
        step=100,
        help="Максимальное значение номинала облигации в условных единицах")

    min_coupon = st.sidebar.number_input(
        "Минимальный купон (у.е.)",
        min_value=0.0,
        max_value=1000.0,
        value=0.0,
        step=10.0,
        help="Минимальная сумма купона в условных единицах")

    # Кнопка обновления данных
    if st.sidebar.button("🔄 Обновить данные", type="primary"):
        # Очистка кеша
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.info(
        "**О коэффициенте Q:**\n\n"
        "Q = (Номинал × Цена) / Купон\n\n"
        "Чем ниже Q, тем больше потенциальный доход (но выше риск).")

    st.sidebar.warning(
        "**Предупреждение!**\n\n"
        "Инвестиции сопряжены с рисками. Проверяйте информацию о дефолтах и рейтинги эмитентов."
    )

    # Получение ключевой ставки ЦБ РФ
    key_rate = get_cbr_key_rate()

    # Информация об обновлении
    # Московское время (UTC+3)
    moscow_tz = timezone(timedelta(hours=3))
    moscow_time = datetime.now(moscow_tz)
    st.write(
        f"**Последнее обновление:** {moscow_time.strftime('%H:%M:%S')} (МСК)")

    # Получение и отображение курсов валют ЦБ РФ
    exchange_rates = get_cbr_exchange_rates()
    st.write(
        f"**Курсы ЦБ РФ:** USD: {exchange_rates['USD']:.2f} ₽ | EUR: {exchange_rates['EUR']:.2f} ₽ | CNY: {exchange_rates['CNY']:.2f} ₽"
    )

    st.markdown("---")

    # Получение и обработка данных
    with st.spinner('Загружаем данные с MOEX...'):
        # Кешируем данные на 5 минут
        @st.cache_data(ttl=300)
        def cached_get_bonds_data():
            return get_moex_bonds_data()

        bonds_data = cached_get_bonds_data()

    if bonds_data is not None:
        with st.spinner('Обрабатываем данные...'):
            processed_data = process_bonds_data(bonds_data, coupon_min,
                                                coupon_max, lot_max,
                                                min_coupon)

        if processed_data is not None and not processed_data.empty:
            # Отображение результатов
            display_df = format_dataframe_for_display(processed_data, key_rate)

            # Метрики
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Найдено облигаций",
                          len(processed_data),
                          help="Количество облигаций после фильтрации")

            with col2:
                avg_yield = processed_data['ANNUAL_YIELD'].mean()
                st.metric(
                    "Средняя доходность",
                    f"{avg_yield:.2f}%",
                    help=
                    "Средняя годовая доходность после вычета НДФЛ 13% по отфильтрованным облигациям"
                )

            with col3:
                st.metric(
                    "Ключевая ставка ЦБ РФ",
                    f"{key_rate:.1f}%",
                    help=
                    "Текущая ключевая ставка Центрального банка Российской Федерации"
                )

            # Анализ распределения облигаций по доходности
            target_bonds = processed_data[
                (processed_data['ANNUAL_YIELD'] >= key_rate)
                & (processed_data['ANNUAL_YIELD'] <= 30)]
            low_yield_bonds = processed_data[processed_data['ANNUAL_YIELD'] <
                                             key_rate]
            high_risk_bonds = processed_data[processed_data['ANNUAL_YIELD'] >
                                             30]

            st.markdown("---")

            # Цветовая легенда и статистика
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"""
                    <div style='background-color: #e8f5e8; padding: 10px; border-radius: 5px;'>
                        <h4 style='color: #1b5e20; margin: 0;'>Норма</h4>
                        <p style='color: #2e7d2e; margin: 5px 0;'>{key_rate}% - 30%</p>
                        <p style='font-size: 18px; font-weight: bold; color: #1b5e20; margin: 0;'>Облигаций: {len(target_bonds)}</p>
                    </div>
                    """,
                            unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                    <div style='background-color: #ffebee; padding: 10px; border-radius: 5px;'>
                        <h4 style='color: #b71c1c; margin: 0;'>Невыгодно</h4>
                        <p style='color: #c62828; margin: 5px 0;'>< {key_rate}%</p>
                        <p style='font-size: 18px; font-weight: bold; color: #b71c1c; margin: 0;'>Облигаций: {len(low_yield_bonds)}</p>
                    </div>
                    """,
                            unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                    <div style='background-color: #fff3e0; padding: 10px; border-radius: 5px;'>
                        <h4 style='color: #e65100; margin: 0;'>Риск</h4>
                        <p style='color: #f57c00; margin: 5px 0;'>> 30%</p>
                        <p style='font-size: 18px; font-weight: bold; color: #e65100; margin: 0;'>Облигаций: {len(high_risk_bonds)}</p>
                    </div>
                    """,
                            unsafe_allow_html=True)

            st.markdown("---")

            # Применяем стили для выделения целевых облигаций
            def highlight_norma_rows(row):
                if row['Категория'] == '🟢 Норма':
                    return ['background-color: rgba(200, 230, 201, 0.15)'
                            ] * len(row)
                else:
                    return [''] * len(row)

            if display_df is not None:
                styled_df = display_df.style.apply(highlight_norma_rows,
                                                   axis=1)
            else:
                styled_df = None

            # Таблица результатов с цветовым индикатором
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Категория":
                    st.column_config.TextColumn("Категория", width="small"),
                    "Название облигации":
                    st.column_config.TextColumn("Название облигации",
                                                width="large"),
                    "Купонный период (дни)":
                    st.column_config.NumberColumn("Купонный период (дни)",
                                                  format="%d"),
                    "Купон (руб.)":
                    st.column_config.NumberColumn("Купон (руб.)",
                                                  format="%.2f ₽"),
                    "Номинал (руб.)":
                    st.column_config.NumberColumn("Номинал (руб.)",
                                                  format="%.2f ₽"),
                    "Цена (%)":
                    st.column_config.NumberColumn("Цена (%)", format="%.3f%%"),
                    "Коэффициент Q":
                    st.column_config.NumberColumn("Коэффициент Q",
                                                  format="%.2f"),
                    "Годовая доходность (%)":
                    st.column_config.NumberColumn("Годовая доходность (%)",
                                                  format="%.2f%%"),
                    "Дата следующего купона":
                    st.column_config.DateColumn("Дата следующего купона",
                                                format="DD.MM.YYYY")
                })

            # Кнопка экспорта в CSV
            st.markdown("---")

            # Подготовка CSV для скачивания
            csv_buffer = io.StringIO()
            processed_data.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_data = csv_buffer.getvalue()

            # Название файла с датой и временем
            filename = f"moex_bonds_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            st.download_button(
                label="📥 Скачать результаты (CSV)",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                help="Скачать отфильтрованные данные в формате CSV")

        else:
            st.warning(
                "⚠️ Нет данных, соответствующих выбранным критериям фильтрации. Попробуйте изменить параметры."
            )

    else:
        st.error("❌ Не удалось получить данные с MOEX. "
                 "Проверьте подключение к интернету и повторите попытку.")

        # Кнопка повторной попытки
        if st.button("🔄 Повторить запрос"):
            st.rerun()

    # Информация в footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666; font-size: 0.8em;'>
        Данные предоставлены MOEX ISS API • 
        <a href='https://iss.moex.com' target='_blank'>Документация API</a> • 
        Обновление каждые 5 минут
        </div>
        """,
                unsafe_allow_html=True)


if __name__ == "__main__":
    main()
