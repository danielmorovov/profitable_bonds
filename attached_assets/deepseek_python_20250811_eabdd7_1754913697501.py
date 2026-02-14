import pandas as pd
import requests

def get_moex_bonds_data():
    """Получает данные об облигациях с MOEX ISS API и возвращает DataFrame"""
    url = "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.xml"
    
    try:
        # Делаем запрос к API
        response = requests.get(url)
        response.raise_for_status()
        
        # Читаем XML и преобразуем в DataFrame
        df = pd.read_xml(response.text, xpath=".//data[@id='securities']/rows/row")
        
        # Получаем дополнительные данные из другого блока (marketdata)
        marketdata_df = pd.read_xml(response.text, xpath=".//data[@id='marketdata']/rows/row")
        
        # Объединяем данные
        merged_df = pd.merge(df, marketdata_df, on='secid', how='inner')
        
        return merged_df
    
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return None

def process_bonds_data(df):
    """Обрабатывает данные об облигациях согласно требованиям"""
    try:
        # Выбираем нужные колонки
        columns = ['SHORTNAME', 'COUPONPERIOD', 'COUPONVALUE', 'LOTVALUE', 'PREVPRICE']
        result_df = df[columns].copy()
        
        # Преобразуем типы данных
        result_df['COUPONPERIOD'] = pd.to_numeric(result_df['COUPONPERIOD'], errors='coerce')
        result_df['COUPONVALUE'] = pd.to_numeric(result_df['COUPONVALUE'], errors='coerce')
        result_df['LOTVALUE'] = pd.to_numeric(result_df['LOTVALUE'], errors='coerce')
        result_df['PREVPRICE'] = pd.to_numeric(result_df['PREVPRICE'], errors='coerce')
        
        # Фильтруем по COUPONPERIOD (25-35 дней)
        filtered_df = result_df[(result_df['COUPONPERIOD'] >= 25) & 
                               (result_df['COUPONPERIOD'] <= 35)].copy()
        
        # Фильтруем по LOTVALUE (не более 1500 руб.)
        filtered_df = filtered_df[filtered_df['LOTVALUE'] <= 1500]
        
        # Рассчитываем коэффициент Q
        filtered_df['Q'] = (filtered_df['LOTVALUE'] * filtered_df['PREVPRICE']) / filtered_df['COUPONVALUE']
        
        # Сортируем по убыванию Q
        sorted_df = filtered_df.sort_values('Q', ascending=False)
        
        # Возвращаем результат без индекса
        return sorted_df.reset_index(drop=True)
    
    except Exception as e:
        print(f"Ошибка при обработке данных: {e}")
        return None

def main():
    # Получаем данные
    bonds_data = get_moex_bonds_data()
    
    if bonds_data is not None:
        # Обрабатываем данные
        processed_data = process_bonds_data(bonds_data)
        
        if processed_data is not None:
            # Выводим результат
            print("Результаты анализа облигаций:")
            print(processed_data.to_string(index=False))
            
            # Сохраняем в CSV
            processed_data.to_csv('moex_bonds_analysis.csv', index=False)
            print("\nРезультаты сохранены в файл 'moex_bonds_analysis.csv'")
        else:
            print("Не удалось обработать данные об облигациях.")
    else:
        print("Не удалось получить данные об облигациях.")

if __name__ == "__main__":
    main()