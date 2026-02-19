# trade_test.py
import datetime
import akshare as ak

def get_market_price(symbol):
    """获取实时价格的独立函数"""
    try:
        if symbol.startswith(('5', '1', '58')):
            df = ak.fund_etf_spot_em()
        else:
            df = ak.stock_zh_a_spot_em()
        
        res = df[df['代码'] == symbol]
        return float(res['最新价'].values[0]) if not res.empty else None
    except:
        return None

def process_buy(user, symbol, quantity):
    price = get_market_price(symbol)
    if not price: return False, "价格获取失败", user
    
    cost = price * quantity
    if user['balance'] < cost: return False, "余额不足", user
    
    # 执行扣款和持仓增加
    user['balance'] -= cost
    user['holdings'][symbol] = user['holdings'].get(symbol, 0) + quantity
    
    # 写入历史记录
    user['history'].append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "买入",
        "code": symbol,
        "price": price,
        "qty": quantity,
        "amount": -cost
    })
    return True, f"成交价: {price}", user

def process_sell(user, symbol, quantity):
    """
    专门处理卖出逻辑
    """
    if user['holdings'].get(symbol, 0) < quantity:
        return False, "持仓不足", user
        
    price = get_market_price(symbol)
    if not price:
        return False, "无法获取价格", user
        
    total_gain = price * quantity
    user['balance'] += total_gain
    user['holdings'][symbol] -= quantity
    
    if user['holdings'][symbol] == 0:
        del user['holdings'][symbol]
    
        # 写入历史记录
    user['history'].append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": "卖出",
        "code": symbol,
        "price": price,
        "qty": quantity,
        "amount": total_gain
    })

    return True, f"以 {price:.3f} 卖出 {quantity}", user

def calculate_total_assets(user):
    """计算当前账户总值（现金+持仓市值）"""
    total_val = user['balance']
    for code, qty in user['holdings'].items():
        price = get_market_price(code) # 实时查价
        if price:
            total_val += price * qty
    return total_val

def update_asset_log(user):
    # 使用“时:分:秒”作为坐标，让曲线随交易即时跳动
    now = datetime.datetime.now().strftime("%H:%M:%S") 
    current_total = calculate_total_assets(user)
    
    # 记录数据点：时间 + 总资产
    user['asset_log'].append({"time": now, "total": current_total})
    
    # 只保留最近的 50 个点，防止 JSON 文件过大
    if len(user['asset_log']) > 50:
        user['asset_log'] = user['asset_log'][-50:]
        
    return user