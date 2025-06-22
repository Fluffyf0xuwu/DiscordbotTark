import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import os
import random
import datetime
import asyncio
from typing import Dict, Optional, List

bot = commands.Bot(command_prefix='+', intents=discord.Intents.all())

# Конфигурация
INVENTORY_FILE = 'inventory.json'
CURRENCY_FILE = 'currency.json'
CASES_FILE = 'cases.json'
ITEMS_PER_PAGE = 5

ALLOWED_ROLE_IDS = [1113130639261179928, 1373964737293058098]  # ID ролей с правами управления
ADMIN_ROLE_IDS = [1113130639261179928, 1373964737293058098]    # ID админских ролей
ITEM_ROLES = {
     "Красная лаб-карта": 1158017931322593290,  # Формат: "Название предмета": ID_роли
    "Зеленая лаб-карта": 1384993037670809610,
    "Желтая лаб-карта": 1384993037704237076,
    "Черная лаб-карта": 1384993037738049696,
    "Фиолетовая лаб-карта": 1384993037863620738,
    "АШ-12": 1384993878809251870,
    "AXMC": 1384993883363999774,
    "Мьёлнер": 1386090540285694022,
    "ETG-Change": 1386090859539464274,
    "Ключ от котеджа": 1386090860378329302,
    "Доступ": 1386090860990566510,
    "Ключ 314 меч.": 1386090860231528628,
}
STARTING_CURRENCY = {
    "Рубли": 100000
}
ITEM_CURRENCY_REWARDS = {
    "Кошелек с рублями": {"Рубли": 5000},
    "Долларовая пачка": {"Доллары": 1000},
    "Евро купюры": {"Евро": 800},
    "Золотой слиток": {"Рубли": 15000, "Доллары": 200},
    "Криптовалюта": {"Доллары": 5000}
}
CURRENCIES = {
    "Рубли": "₽",
    "Доллары": "$",
    "Евро": "€"
}
# Конфигурация
ADMIN_CURRENCY_FILE = 'admin_currency.json'  # Файл для хранения валюты администрации
ADMIN_CURRENCY_NAME = "Админ-валюта"        # Название валюты
ADMIN_CURRENCY_SYMBOL = "⚡"                # Символ валюты

# ID ролей, которые могут управлять админ-валютой
ADMIN_CURRENCY_MANAGER_ROLES = [1113130639261179928, 1373964737293058098]

# ID ролей, которые получают ежедневную выплату и сумма выплаты
DAILY_ADMIN_ROLES = {
    1113130639261179928: 100,  # Формат: ID_роли: сумма_выплаты
    1373964737293058098: 50
}

# Время следующей выплаты (глобальная переменная)
next_daily_payout = None

ADMIN_PAYOUT_CHANNEL_ID = 1386008000640192552  # Замените на реальный ID канала для уведомлений

# --- Система хранения данных ---
def load_data(filename: str) -> dict:
    """Загрузка данных из JSON файла"""
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(data: dict, filename: str):
    """Сохранение данных в JSON файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Система инвентаря ---
class InventoryView(View):
    def __init__(self, ctx, member, items):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.member = member
        self.items = items
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        """Обновляет кнопки для текущей страницы"""
        self.clear_items()
        
        # Кнопки для использования предметов
        start_idx = self.current_page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        
        for i, item in enumerate(self.items[start_idx:end_idx], start_idx):
            # Создаем кнопку только для предметов, которые можно использовать
            if item in ITEM_ROLES or item in ITEM_CURRENCY_REWARDS:
                btn = Button(
                    style=discord.ButtonStyle.green,
                    label=f"Исп. {item[:15]}",
                    custom_id=f"use_{i}"
                )
                btn.callback = lambda interaction, idx=i, it=item: self.use_item(interaction, idx, it)
                self.add_item(btn)
        
        # Кнопки навигации (если предметов больше, чем на одной странице)
        if len(self.items) > ITEMS_PER_PAGE:
            prev_btn = Button(
                style=discord.ButtonStyle.blurple,
                emoji="⬅️",
                disabled=self.current_page == 0
            )
            prev_btn.callback = self.prev_page
            self.add_item(prev_btn)
            
            page_btn = Button(
                style=discord.ButtonStyle.gray,
                label=f"{self.current_page+1}/{(len(self.items)+ITEMS_PER_PAGE-1)//ITEMS_PER_PAGE}",
                disabled=True
            )
            self.add_item(page_btn)
            
            next_btn = Button(
                style=discord.ButtonStyle.blurple,
                emoji="➡️",
                disabled=(self.current_page+1)*ITEMS_PER_PAGE >= len(self.items)
            )
            next_btn.callback = self.next_page
            self.add_item(next_btn)

    async def prev_page(self, interaction):
        """Переход на предыдущую страницу"""
        self.current_page -= 1
        self.update_buttons()
        await self.update_message(interaction)

    async def next_page(self, interaction):
        """Переход на следующую страницу"""
        self.current_page += 1
        self.update_buttons()
        await self.update_message(interaction)

    async def update_message(self, interaction):
        """Обновляет сообщение с новым embed"""
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self):
        """Создает embed для отображения инвентаря"""
        embed = discord.Embed(
            title=f"📦 Инвентарь {self.member.display_name}",
            color=discord.Color.gold()
        )
        
        start_idx = self.current_page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        
        for i, item in enumerate(self.items[start_idx:end_idx], start_idx + 1):
            # Проверяем тип предмета
            if item in ITEM_CURRENCY_REWARDS:
                rewards = ITEM_CURRENCY_REWARDS[item]
                desc = "Дает валюту: " + ", ".join([f"{amt} {CURRENCIES[curr]}" for curr, amt in rewards.items()])
            elif item in ITEM_ROLES:
                role = self.ctx.guild.get_role(ITEM_ROLES[item])
                desc = f"Дает роль: {role.mention}" if role else "Дает роль (не найдена)"
            else:
                desc = "Нельзя использовать"
            
            embed.add_field(
                name=f"#{i}: {item}",
                value=desc,
                inline=False
            )
        
        embed.set_footer(text=f"Страница {self.current_page+1}/{(len(self.items)+ITEMS_PER_PAGE-1)//ITEMS_PER_PAGE} | Всего: {len(self.items)}")
        embed.set_thumbnail(url=self.member.display_avatar.url)
        return embed

    async def use_item(self, interaction, item_idx, item):
        """Обработка использования предмета"""
        try:
            # Проверяем, дает ли предмет валюту
            if item in ITEM_CURRENCY_REWARDS:
                server_id = str(interaction.guild.id)
                user_id = str(interaction.user.id)
                
                # Добавляем валюту
                for currency, amount in ITEM_CURRENCY_REWARDS[item].items():
                    CurrencySystem.update_balance(server_id, user_id, currency, amount)
                
                # Обновляем инвентарь
                inventory = load_data(INVENTORY_FILE)
                if (server_id in inventory and 
                    user_id in inventory[server_id] and 
                    item in inventory[server_id][user_id]):
                    inventory[server_id][user_id].remove(item)
                    save_data(inventory, INVENTORY_FILE)
                    
                    reward_text = ", ".join([f"{amount} {CURRENCIES[currency]}" 
                                          for currency, amount in ITEM_CURRENCY_REWARDS[item].items()])
                    embed = discord.Embed(
                        title="💰 Получена валюта!",
                        description=f"Вы использовали {item} и получили: {reward_text}",
                        color=discord.Color.gold()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    
                    self.items = inventory[server_id][user_id]
                    embed = self.create_embed()
                    await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
                    return
            
            # Проверяем, дает ли предмет роль
            if item in ITEM_ROLES:
                role = interaction.guild.get_role(ITEM_ROLES[item])
                if not role:
                    await interaction.response.send_message("❌ Роль не найдена!", ephemeral=True)
                    return
                
                await self.member.add_roles(role)
                
                # Обновляем инвентарь
                inventory = load_data(INVENTORY_FILE)
                server_id = str(interaction.guild.id)
                user_id = str(self.member.id)
                
                if (server_id in inventory and 
                    user_id in inventory[server_id] and 
                    item in inventory[server_id][user_id]):
                    inventory[server_id][user_id].remove(item)
                    save_data(inventory, INVENTORY_FILE)
                    
                    embed = discord.Embed(
                        title="🎉 Предмет использован",
                        description=f"Вы получили роль {role.mention}!",
                        color=discord.Color.green()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    
                    self.items = inventory[server_id][user_id]
                    embed = self.create_embed()
                    await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
                    return
            
            # Если предмет нельзя использовать
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Этот предмет нельзя использовать!", ephemeral=True)
        
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Ошибка: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)

# --- Команды инвентаря ---
@bot.command(name="инвентарь")
async def show_inventory(ctx, member: Optional[discord.Member] = None):
    """Просмотреть инвентарь"""
    member = member or ctx.author
    inventory = load_data(INVENTORY_FILE)
    server_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    items = inventory.get(server_id, {}).get(user_id, [])
    
    if not items:
        embed = discord.Embed(
            title=f"📦 Инвентарь {member.display_name}",
            description="Инвентарь пуст!",
            color=discord.Color.gold()
        )
        return await ctx.send(embed=embed)
    
    view = InventoryView(ctx, member, items)
    embed = view.create_embed()
    await ctx.send(embed=embed, view=view)

@bot.command(name="добавить")
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def add_item(ctx, member: Optional[discord.Member] = None, *, item: str = None):
    """Добавить предмет в инвентарь"""
    if not item:
        return await ctx.send("❌ Укажите предмет для добавления!")
    
    member = member or ctx.author
    inventory = load_data(INVENTORY_FILE)
    server_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if server_id not in inventory:
        inventory[server_id] = {}
    if user_id not in inventory[server_id]:
        inventory[server_id][user_id] = []
    
    inventory[server_id][user_id].append(item)
    save_data(inventory, INVENTORY_FILE)
    
    embed = discord.Embed(
        title="✅ Предмет добавлен",
        description=f"{member.mention} получил: {item}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="удалить")
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def remove_item(ctx, member: Optional[discord.Member] = None, *, item: str = None):
    """Удалить предмет из инвентаря"""
    if not item:
        return await ctx.send("❌ Укажите предмет для удаления!")
    
    member = member or ctx.author
    inventory = load_data(INVENTORY_FILE)
    server_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if (server_id not in inventory or 
        user_id not in inventory[server_id] or 
        item not in inventory[server_id][user_id]):
        return await ctx.send("❌ Предмет не найден в инвентаре!")
    
    inventory[server_id][user_id].remove(item)
    save_data(inventory, INVENTORY_FILE)
    
    embed = discord.Embed(
        title="🗑️ Предмет удален",
        description=f"Предмет {item} удален у {member.mention}",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

# Команда для очистки инвентаря
@bot.command(name="очистить")
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def clear_inventory(ctx, member: Optional[discord.Member] = None):
    """Очистить инвентарь пользователя (только для админов)"""
    member = member or ctx.author
    inventory = load_data(INVENTORY_FILE)
    server_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if server_id not in inventory or user_id not in inventory[server_id]:
        return await ctx.send(f"❌ Инвентарь {member.mention} уже пуст!")
    
    # Сохраняем количество удаленных предметов для сообщения
    items_count = len(inventory[server_id][user_id])
    
    # Очищаем инвентарь
    inventory[server_id][user_id] = []
    save_data(inventory, INVENTORY_FILE)
    
    embed = discord.Embed(
        title="🗑️ Инвентарь очищен",
        description=f"У {member.mention} удалено {items_count} предметов",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="команды")
async def show_commands(ctx):
    """Показать все доступные команды"""
    embed = discord.Embed(
        title="📜 Список всех команд",
        description="Доступные команды бота:",
        color=discord.Color.blurple()
    )
    
    # Категория: Инвентарь
    embed.add_field(
        name="🎒 **Инвентарь**",
        value=(
            "`+инвентарь [@игрок]` - Посмотреть инвентарь\n"
            "`+добавить [@игрок] <предмет>` - Добавить предмет\n"
            "`+удалить [@игрок] <предмет>` - Удалить предмет\n"
            "`+использовать <предмет>` - Использовать предмет\n"
            "`+рп` - Список предметов за которые выдаются роли\n"
            "`+обмен @игрок` - Начать обмен предметами/валютой\n"
            "`+очистить [@игрок]` - Очистить инвентарь (админ)"
        ),
        inline=False
    )
    
    # Категория: Валюта
    embed.add_field(
        name="💰 **Валюта**",
        value=(
            "`+баланс [@игрок] [валюта]` - Проверить баланс\n"
            "`+добавитьвалюту @игрок <валюта> <сумма>` - Выдать валюту (админ)\n"
            "`+забратьвалюту [@игрок] [валюта] <сумма>` - Забрать валюту (админ)"
            "`+перевод [@игрок] <валюта> <сумма>` - Перевести валюту\n"
            "`+топвалюты [валюта]` - Топ игроков по валюте\n"
            "`+стартоваявалюта [@игрок]` - Выдача стартовых денег"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎁 **Кейсы**",
        value=(
            "`+добавитькейс <название> <валюта> <стоимость> <предметы>` - Добавить кейс (админ)\n"
            "`+удалитькейс <название>` - Удалить кейс (админ)\n"
            "`+списоккейсов` - Показать все кейсы\n"
            "`+открытькейс <название>` - Открыть кейс\n"
            "`+установитьцену <название> <валюта> <стоимость>` - Изменить цену кейса\n"
            "Формат предметов: \"Предмет1:50, Предмет2:30\""
        ),
        inline=False
    )
    
    # Категория: Общее
    embed.add_field(
        name="🔧 **Общее**",
        value=(
            "`+команды` - Показать это сообщение\n"
            "`+проверка` - Проверяет работоспособность бота"
        ),
        inline=False
    )
    embed.add_field(
        name="🔧 **RP команды**",
        value=(
            "`+выпадение [шанс] <предмет>`"
        ),
        inline=False
    )
    
    # Подвал с примерами валют
    embed.set_footer(
        text="Доступные валюты: " + ", ".join(CURRENCIES.keys()) + 
        "\nПример: +добавитьвалюту @Игрок Рубли 100"
    )
    
    await ctx.send(embed=embed)

@bot.command(name="ролевые_предметы", aliases=["рп", "role_items"])
async def show_role_items(ctx):
    """Показать все предметы, которые дают роли или валюту"""
    if not ITEM_ROLES and not ITEM_CURRENCY_REWARDS:
        return await ctx.send("❌ Нет полезных предметов в системе!")
    
    # Создаем embed с пагинацией
    items_per_page = 5
    pages = []
    
    # Собираем все предметы
    all_items = []
    
    # Предметы с ролями
    for item_name, role_id in ITEM_ROLES.items():
        role = ctx.guild.get_role(role_id)
        role_name = role.mention if role else f"❌ Роль (ID: {role_id}) не найдена"
        all_items.append((item_name, f"Дает роль: {role_name}"))
    
    # Предметы с валютой
    for item_name, rewards in ITEM_CURRENCY_REWARDS.items():
        reward_text = ", ".join([f"{amount} {CURRENCIES[currency]}" 
                               for currency, amount in rewards.items()])
        all_items.append((item_name, f"Дает валюту: {reward_text}"))
    
    # Разбиваем на страницы
    for i in range(0, len(all_items), items_per_page):
        page_items = all_items[i:i + items_per_page]
        embed = discord.Embed(
            title="🎁 Полезные предметы",
            description="Список предметов, которые можно использовать:",
            color=discord.Color.gold()
        )
        
        for item_name, description in page_items:
            embed.add_field(
                name=f"🔹 {item_name}",
                value=description,
                inline=False
            )
        
        embed.set_footer(text=f"Страница {len(pages)+1}/{(len(all_items)+items_per_page-1)//items_per_page}")
        pages.append(embed)
    
    # Отправляем первую страницу
    message = await ctx.send(embed=pages[0])
    
    # Добавляем кнопки навигации если страниц больше 1
    if len(pages) > 1:
        current_page = 0
        view = View(timeout=60)
        
        # Кнопка "Назад"
        prev_button = Button(style=discord.ButtonStyle.blurple, emoji="⬅️")
        async def prev_callback(interaction):
            nonlocal current_page
            current_page = max(0, current_page - 1)
            await interaction.response.edit_message(embed=pages[current_page])
        prev_button.callback = prev_callback
        
        # Кнопка "Вперед"
        next_button = Button(style=discord.ButtonStyle.blurple, emoji="➡️")
        async def next_callback(interaction):
            nonlocal current_page
            current_page = min(len(pages)-1, current_page + 1)
            await interaction.response.edit_message(embed=pages[current_page])
        next_button.callback = next_callback
        
        view.add_item(prev_button)
        view.add_item(next_button)
        await message.edit(view=view)

# Файл для хранения валюты
CURRENCY_FILE = 'currency.json'

# Доступные валюты
CURRENCIES = {
    "Рубли": "₽",
    "Доллары": "$",
    "Евро": "€"
}

class CurrencySystem:
    @staticmethod
    def load_currency() -> Dict[str, Dict[str, Dict[str, int]]]:
        """Загружает данные о валюте из файла"""
        if not os.path.exists(CURRENCY_FILE):
            return {}
        with open(CURRENCY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def save_currency(data: Dict[str, Dict[str, Dict[str, int]]]):
        """Сохраняет данные о валюте в файл"""
        with open(CURRENCY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def get_balance(server_id: str, user_id: str, currency: str) -> int:
        """Получает баланс пользователя по валюте"""
        data = CurrencySystem.load_currency()
        return data.get(server_id, {}).get(user_id, {}).get(currency, 0)

    @staticmethod
    def update_balance(server_id: str, user_id: str, currency: str, amount: int):
        """Обновляет баланс пользователя"""
        data = CurrencySystem.load_currency()
        
        if server_id not in data:
            data[server_id] = {}
        if user_id not in data[server_id]:
            data[server_id][user_id] = {}
        
        current = data[server_id][user_id].get(currency, 0)
        data[server_id][user_id][currency] = max(0, current + amount)
        CurrencySystem.save_currency(data)

# Команды для работы с валютой
@bot.command(name="баланс")
async def balance(ctx, member: Optional[discord.Member] = None, currency: Optional[str] = None):
    """Проверить баланс"""
    target = member or ctx.author
    server_id = str(ctx.guild.id)
    user_id = str(target.id)
    
    embed = discord.Embed(
        title=f"💰 Баланс {target.display_name}",
        color=discord.Color.gold()
    )
    
    if currency and currency in CURRENCIES:
        # Проверка конкретной валюты
        balance = CurrencySystem.get_balance(server_id, user_id, currency)
        embed.add_field(
            name=f"{CURRENCIES[currency]} {currency}",
            value=f"**{balance}**",
            inline=False
        )
    else:
        # Показать все валюты
        for curr, symbol in CURRENCIES.items():
            balance = CurrencySystem.get_balance(server_id, user_id, curr)
            embed.add_field(
                name=f"{symbol} {curr}",
                value=f"**{balance}**",
                inline=True
            )
    
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="добавитьвалюту")
@commands.has_permissions(administrator=True)
async def add_currency(ctx, member: discord.Member, currency: str, amount: int):
    """Добавить валюту (только для админов)"""
    if currency not in CURRENCIES:
        return await ctx.send(f"❌ Доступные валюты: {', '.join(CURRENCIES.keys())}")
    
    CurrencySystem.update_balance(str(ctx.guild.id), str(member.id), currency, amount)
    
    embed = discord.Embed(
        title="✅ Валюта добавлена",
        description=f"{member.mention} получил {amount} {CURRENCIES[currency]} {currency}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='забратьвалюту')
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def remove_currency(ctx, member: discord.Member, currency: str, amount: int):
    """Забрать валюту у игрока (только для админов)
    Пример: +забратьвалюту @Игрок Рубли 1000
    """
    if currency not in CURRENCIES:
        return await ctx.send(f"❌ Доступные валюты: {', '.join(CURRENCIES.keys())}")
    
    if amount <= 0:
        return await ctx.send("❌ Сумма должна быть положительной!")
    
    server_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    # Проверка баланса игрока
    current_balance = CurrencySystem.get_balance(server_id, user_id, currency)
    if current_balance < amount:
        return await ctx.send(f"❌ У игрока недостаточно средств! Текущий баланс: {current_balance} {CURRENCIES[currency]}")
    
    # Забираем валюту
    CurrencySystem.update_balance(server_id, user_id, currency, -amount)
    
    embed = discord.Embed(
        title="💰 Валюта изъята",
        description=f"У {member.mention} изъято {amount} {CURRENCIES[currency]} {currency}",
        color=discord.Color.red()
    )
    embed.add_field(
        name="Новый баланс",
        value=f"{CurrencySystem.get_balance(server_id, user_id, currency)} {CURRENCIES[currency]}",
        inline=False
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name="перевод")
async def transfer(ctx, member: discord.Member, currency: str, amount: int):
    """Перевести валюту другому игроку"""
    if currency not in CURRENCIES:
        return await ctx.send(f"❌ Доступные валюты: {', '.join(CURRENCIES.keys())}")
    
    if amount <= 0:
        return await ctx.send("❌ Сумма должна быть положительной!")
    
    server_id = str(ctx.guild.id)
    sender_id = str(ctx.author.id)
    receiver_id = str(member.id)
    
    # Проверка баланса отправителя
    sender_balance = CurrencySystem.get_balance(server_id, sender_id, currency)
    if sender_balance < amount:
        return await ctx.send("❌ Недостаточно средств для перевода!")
    
    # Выполнение перевода
    CurrencySystem.update_balance(server_id, sender_id, currency, -amount)
    CurrencySystem.update_balance(server_id, receiver_id, currency, amount)
    
    embed = discord.Embed(
        title="💸 Перевод выполнен",
        description=f"{ctx.author.mention} перевел {member.mention} {amount} {CURRENCIES[currency]} {currency}",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name="топвалюты")
async def currency_top(ctx, currency: str = "Рубли"):
    """Топ игроков по валюте"""
    if currency not in CURRENCIES:
        return await ctx.send(f"❌ Доступные валюты: {', '.join(CURRENCIES.keys())}")
    
    data = CurrencySystem.load_currency()
    server_data = data.get(str(ctx.guild.id), {})
    
    # Сбор и сортировка данных
    top_players = []
    for user_id, currencies in server_data.items():
        if currency in currencies:
            member = ctx.guild.get_member(int(user_id))
            if member:
                top_players.append((member.display_name, currencies[currency]))
    
    top_players.sort(key=lambda x: x[1], reverse=True)
    
    # Формирование embed
    embed = discord.Embed(
        title=f"🏆 Топ по {currency} {CURRENCIES[currency]}",
        color=discord.Color.dark_gold()
    )
    
    for i, (name, amount) in enumerate(top_players[:10], 1):
        embed.add_field(
            name=f"{i}. {name}",
            value=f"{amount} {CURRENCIES[currency]}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='выпадение')
async def drop_check(ctx, chance: int, *, item_name: str):
    """Проверить выпадение предмета
    Пример: +выпадение 15 Алмаз
    """
    try:
        # Проверка корректности шанса
        if chance < 1 or chance > 100:
            await ctx.send("❌ Шанс должен быть от 1 до 100%")
            return
        
        # Генерация случайного числа
        roll = random.randint(1, 100)
        success = roll <= chance
        
        # Создаем красивый embed
        embed = discord.Embed(
            color=discord.Color.gold() if success else discord.Color.dark_grey()
        )
        
        if success:
            embed.title = f"🎉 Выпал {item_name}!"
            embed.description = f"Выпал предмет **{item_name}** с шансом {chance}%!"
            embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/160/twitter/282/party-popper_1f389.png")
        else:
            embed.title = f"❌ {item_name} не выпал"
            embed.description = f"Предмет **{item_name}** не выпал (шанс {chance}%)"
            embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/160/twitter/282/cross-mark_274c.png")
        
        # Добавляем поле с результатом броска
        embed.add_field(
            name="Результат броска",
            value=f"Выпало число: {roll}/{chance}",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Произошла ошибка: {str(e)}")

# Добавим обработчик события on_member_join
@bot.event
async def on_member_join(member):
    """Выдаем стартовую валюту новому участнику"""
    server_id = str(member.guild.id)
    user_id = str(member.id)
    
    # Проверяем, есть ли уже данные у пользователя (чтобы не выдавать повторно)
    data = CurrencySystem.load_currency()
    if server_id in data and user_id in data[server_id]:
        return  # У пользователя уже есть записи о валюте
    
    # Выдаем стартовую валюту
    for currency, amount in STARTING_CURRENCY.items():
        CurrencySystem.update_balance(server_id, user_id, currency, amount)
    
    # Можно добавить лог в консоль
    print(f"Выдана стартовая валюта новому участнику: {member.display_name}")

# Также добавим команду для ручной выдачи стартовой валюты
@bot.command(name="стартоваявалюта", aliases=["стартвал", "startcurrency"])
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def give_starting_currency(ctx, member: Optional[discord.Member] = None):
    """Выдать стартовую валюту пользователю (админ)"""
    member = member or ctx.author
    server_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    # Проверяем, есть ли уже данные у пользователя
    data = CurrencySystem.load_currency()
    if server_id in data and user_id in data[server_id]:
        # Проверяем, выдавалась ли уже стартовая валюта
        for currency in STARTING_CURRENCY:
            if currency in data[server_id][user_id]:
                return await ctx.send(f"❌ {member.mention} уже получал стартовую валюту!")
    
    # Выдаем стартовую валюту
    for currency, amount in STARTING_CURRENCY.items():
        CurrencySystem.update_balance(server_id, user_id, currency, amount)
    
    embed = discord.Embed(
        title="💰 Стартовая валюта выдана",
        description=f"{member.mention} получил стартовую валюту:",
        color=discord.Color.green()
    )
    
    for currency, amount in STARTING_CURRENCY.items():
        embed.add_field(
            name=f"{CURRENCIES[currency]} {currency}",
            value=f"**{amount}**",
            inline=True
        )
    
    await ctx.send(embed=embed)

# Класс для работы с кейсами
class CaseSystem:
    @staticmethod
    def load_cases():
        """Загружает кейсы из файла"""
        if not os.path.exists(CASES_FILE):
            return {}
        
        try:
            with open(CASES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Конвертируем старый формат в новый, если необходимо
                if isinstance(data, list):
                    new_data = {}
                    for case in data:
                        if isinstance(case, dict) and "name" in case and "items" in case:
                            new_data[case["name"]] = {
                                "items": case["items"],
                                "price": {
                                    "currency": None,
                                    "amount": 0
                                }
                            }
                    if new_data:
                        CaseSystem.save_cases(new_data)
                        return new_data
                    return {}
                
                return data
        except:
            return {}

    @staticmethod
    def save_cases(data):
        """Сохраняет кейсы в файл"""
        with open(CASES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def add_case(case_name, items, price_currency=None, price_amount=0):
        """Добавляет новый кейс"""
        cases = CaseSystem.load_cases()
        cases[case_name] = {
            "items": items,
            "price": {
                "currency": price_currency,
                "amount": price_amount
            }
        }
        CaseSystem.save_cases(cases)

    @staticmethod
    def remove_case(case_name):
        """Удаляет кейс"""
        cases = CaseSystem.load_cases()
        if case_name in cases:
            del cases[case_name]
            CaseSystem.save_cases(cases)
            return True
        return False

    @staticmethod
    def get_random_item(case_name):
        """Получает случайный предмет из кейса"""
        cases = CaseSystem.load_cases()
        if case_name not in cases:
            return None
        
        items = cases[case_name]["items"]
        if not items:
            return None
            
        total_weight = sum(item['chance'] for item in items)
        roll = random.uniform(0, total_weight)
        current = 0
        
        for item in items:
            current += item['chance']
            if roll <= current:
                return item['item']
        return None

    @staticmethod
    def set_case_price(case_name, currency, amount):
        """Устанавливает цену кейса"""
        cases = CaseSystem.load_cases()
        if case_name not in cases:
            return False
        
        cases[case_name]["price"] = {
            "currency": currency,
            "amount": amount
        }
        CaseSystem.save_cases(cases)
        return True

# Команды для работы с кейсами
@bot.command(name='добавитькейс')
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def add_case(ctx, case_name: str, price_currency: str = None, price_amount: int = 0, *, items: str):
    """Добавить новый кейс с предметами
    Формат: +добавитькейс НазваниеКейса [валюта] [цена] "Предмет с пробелами":50 "Другой предмет":30
    Пример: +добавитькейс Оружие Рубли 1000 "АШ-12":30 "AXMC снайперская":20
    """
    try:
        # Если цена указана, но валюта не указана
        if price_amount and not price_currency:
            return await ctx.send("❌ Укажите валюту для цены кейса!")
            
        # Проверка валюты, если указана цена
        if price_amount > 0 and price_currency not in CURRENCIES:
            return await ctx.send(f"❌ Неверная валюта. Доступные: {', '.join(CURRENCIES.keys())}")

        items_list = []
        # Используем регулярное выражение для парсинга элементов с кавычками
        import re
        pattern = r'("[^"]+"|\'[^\']+\'|\S+):(\d+)'
        matches = re.findall(pattern, items)
        
        if not matches:
            return await ctx.send("❌ Неверный формат предметов. Используйте: \"Предмет с пробелами\":50 или Предмет:30")
        
        for item_match in matches:
            item_name = item_match[0].strip('"\'')  # Удаляем кавычки если они есть
            try:
                chance_value = int(item_match[1])
                if chance_value <= 0:
                    await ctx.send(f"❌ Шанс должен быть положительным числом: `{item_match[0]}:{item_match[1]}`")
                    return
                
                items_list.append({
                    'item': item_name,
                    'chance': chance_value
                })
            except ValueError:
                await ctx.send(f"❌ Неверный формат шанса в предмете: `{item_match[0]}:{item_match[1]}`")
                return

        CaseSystem.add_case(case_name, items_list, price_currency, price_amount)
        
        embed = discord.Embed(
            title="✅ Кейс добавлен",
            description=f"Кейс **{case_name}** успешно создан!",
            color=discord.Color.green()
        )
        
        # Добавляем цену, если указана
        if price_amount > 0:
            embed.add_field(
                name="💰 Цена",
                value=f"{price_amount} {CURRENCIES[price_currency]} {price_currency}",
                inline=False
            )
        else:
            embed.add_field(
                name="💰 Цена",
                value="Бесплатно",
                inline=False
            )
        
        # Добавляем список предметов
        for item in items_list:
            embed.add_field(
                name=f"🔹 {item['item']}",
                value=f"Шанс: {item['chance']}%",
                inline=False
            )
            
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(
            "❌ Ошибка при создании кейса. Примеры правильного использования:\n"
            "`+добавитькейс Оружие Рубли 1000 \"АШ-12\":30 \"AXMC снайперская\":20`\n"
            "`+добавитькейс Лаборатория Доллары 500 \"Красная карта\":40 \"Зеленая карта\":30`\n"
            f"Ошибка: {str(e)}"
        )

@bot.command(name='установитьцену')
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def set_case_price(ctx, case_name: str, currency: str, amount: int):
    """Установить цену кейса в валюте"""
    if currency not in CURRENCIES:
        return await ctx.send(f"❌ Неверная валюта. Доступные: {', '.join(CURRENCIES.keys())}")
    
    if amount < 0:
        return await ctx.send("❌ Цена не может быть отрицательной!")
    
    if CaseSystem.set_case_price(case_name, currency, amount):
        embed = discord.Embed(
            title="✅ Цена кейса обновлена",
            description=f"Кейс **{case_name}** теперь стоит {amount} {CURRENCIES[currency]} {currency}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Кейс **{case_name}** не найден!")

@bot.command(name='списоккейсов')
async def list_cases(ctx):
    """Показать список всех кейсов с ценами"""
    cases = CaseSystem.load_cases()
    
    if not cases:
        return await ctx.send("❌ На сервере нет доступных кейсов!")
    
    embed = discord.Embed(
        title="📦 Доступные кейсы",
        color=discord.Color.gold()
    )
    
    for case_name, case_data in cases.items():
        # Проверяем структуру данных
        if isinstance(case_data, dict):
            items = case_data.get("items", [])
            price_info = case_data.get("price", {"currency": None, "amount": 0})
        else:
            # Старый формат данных (только список предметов)
            items = case_data
            price_info = {"currency": None, "amount": 0}
        
        items_list = "\n".join(f"• {item['item']} ({item['chance']}%)" for item in items) if items else "Нет предметов"
        
        if price_info.get("amount", 0) > 0 and price_info.get("currency") in CURRENCIES:
            price_text = f"{price_info['amount']} {CURRENCIES[price_info['currency']]} {price_info['currency']}"
        else:
            price_text = "Бесплатно"
        
        embed.add_field(
            name=f"🔸 {case_name} - {price_text}",
            value=items_list,
            inline=False
        )
    
    await ctx.send(embed=embed)
@bot.command(name='удалитькейс')
@commands.has_any_role(*ALLOWED_ROLE_IDS, *ADMIN_ROLE_IDS)
async def remove_case_command(ctx, case_name: str):
    """Удалить кейс"""
    if CaseSystem.remove_case(case_name):
        embed = discord.Embed(
            title="✅ Кейс удален",
            description=f"Кейс **{case_name}** был успешно удален!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Ошибка",
            description=f"Кейс **{case_name}** не найден!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@bot.command(name='открытькейс')
async def open_case(ctx, case_name: str):
    """Открыть кейс (платно, если установлена цена)"""
    cases = CaseSystem.load_cases()
    
    if case_name not in cases:
        return await ctx.send(f"❌ Кейс **{case_name}** не найден!")
    
    case_data = cases[case_name]
    
    # Обрабатываем разные форматы данных
    if isinstance(case_data, dict):
        items = case_data.get("items", [])
        price_info = case_data.get("price", {"currency": None, "amount": 0})
    else:
        items = case_data
        price_info = {"currency": None, "amount": 0}
    
    if not items:
        return await ctx.send(f"❌ Кейс **{case_name}** пуст!")
    
    # Проверяем, нужно ли платить за кейс
    if price_info.get("amount", 0) > 0 and price_info.get("currency") in CURRENCIES:
        currency = price_info["currency"]
        amount = price_info["amount"]
        
        # Проверяем баланс пользователя
        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        balance = CurrencySystem.get_balance(server_id, user_id, currency)
        
        if balance < amount:
            return await ctx.send(
                f"❌ Недостаточно средств! Для открытия кейса нужно {amount} {CURRENCIES[currency]} {currency}\n"
                f"Ваш баланс: {balance} {CURRENCIES[currency]}"
            )
        
        # Снимаем валюту
        CurrencySystem.update_balance(server_id, user_id, currency, -amount)
    
    # Получаем случайный предмет
    item = CaseSystem.get_random_item(case_name)
    if not item:
        return await ctx.send("❌ Произошла ошибка при открытии кейса!")
    
    # Добавляем предмет в инвентарь
    inventory = load_data(INVENTORY_FILE)
    server_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)
    
    if server_id not in inventory:
        inventory[server_id] = {}
    if user_id not in inventory[server_id]:
        inventory[server_id][user_id] = []
    
    inventory[server_id][user_id].append(item)
    save_data(inventory, INVENTORY_FILE)
    
    # Создаем красивый embed
    embed = discord.Embed(
        title=f"🎉 Вы открыли кейс {case_name}!",
        description=f"Вам выпал: **{item}**",
        color=discord.Color.gold()
    )
    
    # Если была цена, указываем это
    if price_info.get("amount", 0) > 0 and price_info.get("currency") in CURRENCIES:
        embed.add_field(
            name="💰 Стоимость",
            value=f"Потрачено: {price_info['amount']} {CURRENCIES[price_info['currency']]} {price_info['currency']}",
            inline=False
        )
    
    # Если предмет дает роль, указываем это
    if item in ITEM_ROLES:
        role = ctx.guild.get_role(ITEM_ROLES[item])
        if role:
            embed.add_field(
                name="🔹 Особенность",
                value=f"Этот предмет дает роль {role.mention}",
                inline=False
            )
    
    embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/160/twitter/282/package_1f4e6.png")
    embed.set_footer(text=f"Кейс открыл: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command(name='проверка')
async def check_bot(ctx):
    """Проверить работоспособность бота"""
    # Создаем embed для отчета
    embed = discord.Embed(
        title="🔍 Проверка работоспособности бота",
        description="Проверяем основные системы...",
        color=discord.Color.blue()
    )
    
    # Проверяем системы одну за другой
    checks = []
    
    # 1. Проверка файлов данных
    try:
        files_to_check = [INVENTORY_FILE, CURRENCY_FILE, CASES_FILE]
        files_ok = True
        for file in files_to_check:
            if not os.path.exists(file):
                # Попробуем создать файл, если его нет
                with open(file, 'w') as f:
                    json.dump({}, f)
        checks.append("✅ Файлы данных доступны и созданы при необходимости")
    except Exception as e:
        checks.append(f"❌ Ошибка работы с файлами данных: {str(e)}")
    
    # 2. Проверка системы инвентаря
    try:
        test_data = {"test_server": {"test_user": ["test_item"]}}
        save_data(test_data, INVENTORY_FILE)
        loaded = load_data(INVENTORY_FILE)
        if loaded.get("test_server", {}).get("test_user") == ["test_item"]:
            checks.append("✅ Система инвентаря работает корректно")
        else:
            checks.append("❌ Ошибка в системе инвентаря: данные не сохраняются/загружаются")
        # Удаляем тестовые данные
        if "test_server" in loaded:
            del loaded["test_server"]
            save_data(loaded, INVENTORY_FILE)
    except Exception as e:
        checks.append(f"❌ Ошибка в системе инвентаря: {str(e)}")
    
    # 3. Проверка системы валюты
    try:
        CurrencySystem.update_balance("test_server", "test_user", "Рубли", 1000)
        balance = CurrencySystem.get_balance("test_server", "test_user", "Рубли")
        if balance == 1000:
            checks.append("✅ Система валюты работает корректно")
        else:
            checks.append("❌ Ошибка в системе валюты: баланс не сохраняется")
        # Очищаем тестовые данные
        data = CurrencySystem.load_currency()
        if "test_server" in data:
            del data["test_server"]
            CurrencySystem.save_currency(data)
    except Exception as e:
        checks.append(f"❌ Ошибка в системе валюты: {str(e)}")
    
    # 4. Проверка системы кейсов
    try:
        test_case = {
            "items": [{"item": "test_item", "chance": 100}],
            "price": {"currency": "Рубли", "amount": 100}
        }
        cases = CaseSystem.load_cases()
        cases["test_case"] = test_case
        CaseSystem.save_cases(cases)
        
        loaded_cases = CaseSystem.load_cases()
        if loaded_cases.get("test_case"):
            checks.append("✅ Система кейсов работает корректно")
        else:
            checks.append("❌ Ошибка в системе кейсов: данные не сохраняются")
        
        # Удаляем тестовый кейс
        if "test_case" in loaded_cases:
            del loaded_cases["test_case"]
            CaseSystem.save_cases(loaded_cases)
    except Exception as e:
        checks.append(f"❌ Ошибка в системе кейсов: {str(e)}")
    
    # 5. Проверка подключения к Discord
    try:
        latency = round(bot.latency * 1000)  # в мс
        checks.append(f"✅ Подключение к Discord: задержка {latency}мс")
    except Exception as e:
        checks.append(f"❌ Ошибка подключения к Discord: {str(e)}")
    
    # Добавляем все проверки в embed
    for i, check in enumerate(checks, 1):
        embed.add_field(
            name=f"Проверка #{i}",
            value=check,
            inline=False
        )
    
    # Общий статус
    if all("✅" in check for check in checks):
        embed.color = discord.Color.green()
        embed.set_footer(text="Все системы работают нормально")
    else:
        embed.color = discord.Color.orange()
        embed.set_footer(text="Обнаружены проблемы в некоторых системах")
    
    await ctx.send(embed=embed)

class AdminCurrencySystem:
    @staticmethod
    def load_admin_currency() -> Dict[str, Dict[str, int]]:
        """Загружает данные о валюте администрации из файла"""
        if not os.path.exists(ADMIN_CURRENCY_FILE):
            return {}
        try:
            with open(ADMIN_CURRENCY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    def save_admin_currency(data: Dict[str, Dict[str, int]]):
        """Сохраняет данные о валюте администрации в файл"""
        with open(ADMIN_CURRENCY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def get_balance(server_id: str, user_id: str) -> int:
        """Получает баланс пользователя по админ-валюте"""
        data = AdminCurrencySystem.load_admin_currency()
        return data.get(server_id, {}).get(user_id, 0)

    @staticmethod
    def update_balance(server_id: str, user_id: str, amount: int):
        """Обновляет баланс пользователя (только добавление)"""
        if amount <= 0:
            return
        
        data = AdminCurrencySystem.load_admin_currency()
        
        if server_id not in data:
            data[server_id] = {}
        if user_id not in data[server_id]:
            data[server_id][user_id] = 0
        
        data[server_id][user_id] = max(0, data[server_id][user_id] + amount)
        AdminCurrencySystem.save_admin_currency(data)

    @staticmethod
    async def process_daily_payout(guild: discord.Guild):
        """Обработка ежедневной выплаты админ-валюты"""
        global next_daily_payout
        
        # Проверяем, нужно ли делать выплату
        now = datetime.datetime.now()
        if next_daily_payout and now < next_daily_payout:
            return
        
        # Устанавливаем следующее время выплаты (через 24 часа)
        next_daily_payout = now + datetime.timedelta(hours=24)
        
        server_id = str(guild.id)
        payout_log = []
        payout_embed = discord.Embed(
            title=f"{ADMIN_CURRENCY_SYMBOL} Ежедневная выплата {ADMIN_CURRENCY_NAME}",
            color=discord.Color.purple()
        )
        
        for role_id, amount in DAILY_ADMIN_ROLES.items():
            role = guild.get_role(role_id)
            if not role:
                continue
                
            for member in role.members:
                AdminCurrencySystem.update_balance(server_id, str(member.id), amount)
                payout_log.append(f"{member.mention} ({role.name}): +{amount}{ADMIN_CURRENCY_SYMBOL}")
        
        # Отправляем уведомление в канал
        if payout_log:
            payout_embed.description = "\n".join(payout_log)
            payout_embed.set_footer(text=f"Следующая выплата: {next_daily_payout.strftime('%d.%m.%Y в %H:%M')}")
            
            channel = guild.get_channel(ADMIN_PAYOUT_CHANNEL_ID)
            if channel:
                try:
                    await channel.send(embed=payout_embed)
                except Exception as e:
                    print(f"Не удалось отправить уведомление о выплате: {str(e)}")
            
            # Логируем выплату в консоль
            print(f"[Admin Currency] Ежедневная выплата выполнена:\n" + "\n".join(payout_log))

# Команды для работы с админ-валютой
@bot.command(name='админбаланс')
async def admin_balance(ctx, member: Optional[discord.Member] = None):
    """Проверить баланс админ-валюты"""
    member = member or ctx.author
    server_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    balance = AdminCurrencySystem.get_balance(server_id, user_id)
    
    embed = discord.Embed(
        title=f"{ADMIN_CURRENCY_SYMBOL} Баланс админ-валюты {member.display_name}",
        description=f"**{balance} {ADMIN_CURRENCY_NAME}** {ADMIN_CURRENCY_SYMBOL}",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@bot.command(name='выдатьадминвалюту')
@commands.has_any_role(*ADMIN_CURRENCY_MANAGER_ROLES)
async def add_admin_currency(ctx, member: discord.Member, amount: int):
    """Выдать админ-валюту (только для управляющих)"""
    if amount <= 0:
        return await ctx.send("❌ Сумма должна быть положительной!")
    
    AdminCurrencySystem.update_balance(str(ctx.guild.id), str(member.id), amount)
    
    embed = discord.Embed(
        title="✅ Валюта выдана",
        description=f"{member.mention} получил {amount}{ADMIN_CURRENCY_SYMBOL} {ADMIN_CURRENCY_NAME}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='топадминвалюты')
async def admin_currency_top(ctx):
    """Топ игроков по админ-валюте"""
    data = AdminCurrencySystem.load_admin_currency()
    server_data = data.get(str(ctx.guild.id), {})
    
    # Сбор и сортировка данных
    top_players = []
    for user_id, amount in server_data.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            top_players.append((member.display_name, amount))
    
    top_players.sort(key=lambda x: x[1], reverse=True)
    
    # Формирование embed
    embed = discord.Embed(
        title=f"🏆 Топ по {ADMIN_CURRENCY_NAME} {ADMIN_CURRENCY_SYMBOL}",
        color=discord.Color.purple()
    )
    
    for i, (name, amount) in enumerate(top_players[:10], 1):
        embed.add_field(
            name=f"{i}. {name}",
            value=f"{amount}{ADMIN_CURRENCY_SYMBOL}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='следующаявыплата', aliases=['nextpayout'])
async def next_payout(ctx):
    """Показать время до следующей выплаты админ-валюты"""
    global next_daily_payout
    
    if not next_daily_payout:
        # Если выплата еще не производилась, устанавливаем следующее время
        now = datetime.datetime.now()
        next_daily_payout = now + datetime.timedelta(hours=24)
        await AdminCurrencySystem.process_daily_payout(ctx.guild)
    
    now = datetime.datetime.now()
    if now >= next_daily_payout:
        embed = discord.Embed(
            title=f"{ADMIN_CURRENCY_SYMBOL} Выплата админ-валюты",
            description="Следующая выплата должна произойти в любое время!",
            color=discord.Color.gold()
        )
    else:
        time_left = next_daily_payout - now
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed = discord.Embed(
            title=f"{ADMIN_CURRENCY_SYMBOL} Время до следующей выплаты",
            description=f"Следующая выплата {ADMIN_CURRENCY_NAME} произойдет через:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Осталось времени:",
            value=f"{time_left.days} дней, {hours} часов, {minutes} минут",
            inline=False
        )
        embed.add_field(
            name="Точное время выплаты:",
            value=next_daily_payout.strftime("%d.%m.%Y в %H:%M"),
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='админ')
@commands.has_any_role(*ADMIN_ROLE_IDS)
async def admin_commands(ctx):
    """Показать все команды для администрации"""
    embed = discord.Embed(
        title="🛠️ Команды для администрации",
        description="Список доступных команд для администраторов сервера:",
        color=discord.Color.dark_gold()
    )
    
    # Категория: Управление предметами
    embed.add_field(
        name="📦 **Управление предметами**",
        value=(
            "`+добавить [@игрок] <предмет>` - Добавить предмет в инвентарь\n"
            "`+удалить [@игрок] <предмет>` - Удалить предмет из инвентаря\n"
            "`+очистить [@игрок]` - Очистить инвентарь игрока\n"
            "`+рп` - Список предметов, дающих роли"
        ),
        inline=False
    )
    
    # Категория: Управление валютой
    embed.add_field(
        name="💰 **Управление валютой**",
        value=(
            "`+добавитьвалюту @игрок <валюта> <сумма>` - Выдать валюту\n"
            "`+забратьвалюту @игрок <валюта> <сумма>` - Забрать валюту\n"
            "`+стартоваявалюта [@игрок]` - Выдать стартовую валюту\n"
            "`+выдатьадминвалюту @игрок <сумма>` - Выдать админ-валюту\n"
            "`+топадминвалюты` - Топ по админ-валюте"
        ),
        inline=False
    )
    
    # Категория: Управление кейсами
    embed.add_field(
        name="🎁 **Управление кейсами**",
        value=(
            "`+добавитькейс <название> <валюта> <стоимость> <предметы>` - Создать кейс\n"
            "`+удалитькейс <название>` - Удалить кейс\n"
            "`+установитьцену <название> <валюта> <стоимость>` - Изменить цену кейса\n"
            "`+списоккейсов` - Показать все кейсы"
        ),
        inline=False
    )
    
    # Категория: Системные команды
    embed.add_field(
        name="⚙️ **Системные команды**",
        value=(
            "`+проверка` - Проверить работоспособность бота\n"
            "`+следующаявыплата` - Время до следующей выплаты админ-валюты"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"Запрошено администратором: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} запущен!')
    # Запускаем фоновую задачу для выплат
    bot.loop.create_task(daily_payout_task())

async def daily_payout_task():
    await bot.wait_until_ready()  # Ждем, пока бот полностью запустится
    while not bot.is_closed():
        for guild in bot.guilds:
            await AdminCurrencySystem.process_daily_payout(guild)
        await asyncio.sleep(3600)  # Проверка каждый час

# Добавляем новый класс для интерфейса обмена
class TradeView(View):
    def __init__(self, ctx, initiator: discord.Member, recipient: discord.Member, initiator_items: List[str], recipient_items: List[str], initiator_currency: Dict[str, int], recipient_currency: Dict[str, int]):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.initiator = initiator
        self.recipient = recipient
        self.initiator_items = initiator_items
        self.recipient_items = recipient_items
        self.initiator_currency = initiator_currency
        self.recipient_currency = recipient_currency
        self.confirmations = set()
        
        # Добавляем кнопки
        self.add_item(Button(style=discord.ButtonStyle.green, label="Подтвердить", custom_id="confirm"))
        self.add_item(Button(style=discord.ButtonStyle.red, label="Отменить", custom_id="cancel"))
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Проверяем, что взаимодействие от одного из участников обмена
        return interaction.user.id in [self.initiator.id, self.recipient.id]
    
    async def update_embed(self):
        embed = discord.Embed(
            title="🔁 Обмен предметами",
            description=f"Обмен между {self.initiator.mention} и {self.recipient.mention}",
            color=discord.Color.blue()
        )
        
        # Предметы и валюта инициатора
        initiator_text = "**Предметы:**\n"
        initiator_text += "\n".join(f"• {item}" for item in self.initiator_items) if self.initiator_items else "Нет предметов"
        
        initiator_text += "\n\n**Валюта:**\n"
        initiator_text += "\n".join(f"• {amount} {CURRENCIES[currency]}" for currency, amount in self.initiator_currency.items()) if self.initiator_currency else "Нет валюты"
        
        # Предметы и валюта получателя
        recipient_text = "**Предметы:**\n"
        recipient_text += "\n".join(f"• {item}" for item in self.recipient_items) if self.recipient_items else "Нет предметов"
        
        recipient_text += "\n\n**Валюта:**\n"
        recipient_text += "\n".join(f"• {amount} {CURRENCIES[currency]}" for currency, amount in self.recipient_currency.items()) if self.recipient_currency else "Нет валюты"
        
        embed.add_field(name=f"От {self.initiator.display_name}", value=initiator_text, inline=True)
        embed.add_field(name=f"К {self.recipient.display_name}", value=recipient_text, inline=True)
        
        # Статус подтверждения
        status = []
        if self.initiator.id in self.confirmations:
            status.append(f"{self.initiator.display_name} ✅")
        else:
            status.append(f"{self.initiator.display_name} ❌")
            
        if self.recipient.id in self.confirmations:
            status.append(f"{self.recipient.display_name} ✅")
        else:
            status.append(f"{self.recipient.display_name} ❌")
            
        embed.add_field(name="Подтверждения", value="\n".join(status), inline=False)
        
        return embed
    
    @discord.ui.button(style=discord.ButtonStyle.green, label="Подтвердить", custom_id="confirm")
    async def confirm_callback(self, interaction: discord.Interaction, button: Button):
        self.confirmations.add(interaction.user.id)
        
        if len(self.confirmations) == 2:
            # Оба подтвердили - выполняем обмен
            await self.execute_trade()
            embed = await self.update_embed()
            embed.title = "✅ Обмен завершен!"
            embed.color = discord.Color.green()
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            # Ждем второго подтверждения
            embed = await self.update_embed()
            await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(style=discord.ButtonStyle.red, label="Отменить", custom_id="cancel")
    async def cancel_callback(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="❌ Обмен отменен",
            description=f"{interaction.user.mention} отменил обмен",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    async def execute_trade(self):
        # Обновляем инвентари
        inventory = load_data(INVENTORY_FILE)
        server_id = str(self.ctx.guild.id)
        
        # Инициатор
        if server_id not in inventory:
            inventory[server_id] = {}
        if str(self.initiator.id) not in inventory[server_id]:
            inventory[server_id][str(self.initiator.id)] = []
        if str(self.recipient.id) not in inventory[server_id]:
            inventory[server_id][str(self.recipient.id)] = []
        
        # Удаляем предметы у инициатора и добавляем получателю
        for item in self.initiator_items:
            if item in inventory[server_id][str(self.initiator.id)]:
                inventory[server_id][str(self.initiator.id)].remove(item)
                inventory[server_id][str(self.recipient.id)].append(item)
        
        # Удаляем предметы у получателя и добавляем инициатору
        for item in self.recipient_items:
            if item in inventory[server_id][str(self.recipient.id)]:
                inventory[server_id][str(self.recipient.id)].remove(item)
                inventory[server_id][str(self.initiator.id)].append(item)
        
        save_data(inventory, INVENTORY_FILE)
        
        # Обновляем валюту
        for currency, amount in self.initiator_currency.items():
            CurrencySystem.update_balance(server_id, str(self.initiator.id), currency, -amount)
            CurrencySystem.update_balance(server_id, str(self.recipient.id), currency, amount)
            
        for currency, amount in self.recipient_currency.items():
            CurrencySystem.update_balance(server_id, str(self.recipient.id), currency, -amount)
            CurrencySystem.update_balance(server_id, str(self.initiator.id), currency, amount)

# Команда для начала обмена
@bot.command(name='обмен')
async def trade(ctx, member: discord.Member):
    """Начать обмен предметами с другим игроком"""
    if member == ctx.author:
        return await ctx.send("❌ Нельзя обмениваться с самим собой!")
    
    # Загружаем инвентари
    inventory = load_data(INVENTORY_FILE)
    server_id = str(ctx.guild.id)
    
    initiator_items = inventory.get(server_id, {}).get(str(ctx.author.id), [])
    recipient_items = inventory.get(server_id, {}).get(str(member.id), [])
    
    # Создаем интерфейс обмена
    view = TradeView(ctx, ctx.author, member, [], [], {}, {})
    embed = await view.update_embed()
    
    # Создаем View для выбора предметов
    class TradeSetupView(View):
        def __init__(self, trade_view: TradeView):
            super().__init__(timeout=300)
            self.trade_view = trade_view
            
        @discord.ui.button(label="Выбрать предметы", style=discord.ButtonStyle.blurple)
        async def select_items(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id not in [self.trade_view.initiator.id, self.trade_view.recipient.id]:
                await interaction.response.send_message("❌ Вы не участник этого обмена!", ephemeral=True)
                return
                
            # Создаем модальное окно для выбора предметов
            modal = ItemSelectModal(self.trade_view, interaction.user.id == self.trade_view.initiator.id)
            await interaction.response.send_modal(modal)
            
        @discord.ui.button(label="Выбрать валюту", style=discord.ButtonStyle.blurple)
        async def select_currency(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id not in [self.trade_view.initiator.id, self.trade_view.recipient.id]:
                await interaction.response.send_message("❌ Вы не участник этого обмена!", ephemeral=True)
                return
                
            # Создаем модальное окно для выбора валюты
            modal = CurrencySelectModal(self.trade_view, interaction.user.id == self.trade_view.initiator.id)
            await interaction.response.send_modal(modal)
            
        @discord.ui.button(label="Подтвердить обмен", style=discord.ButtonStyle.green)
        async def confirm_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id not in [self.trade_view.initiator.id, self.trade_view.recipient.id]:
                await interaction.response.send_message("❌ Вы не участник этого обмена!", ephemeral=True)
                return
                
            self.trade_view.confirmations.add(interaction.user.id)
            
            if len(self.trade_view.confirmations) == 2:
                # Оба подтвердили - выполняем обмен
                await self.trade_view.execute_trade()
                embed = await self.trade_view.update_embed()
                embed.title = "✅ Обмен завершен!"
                embed.color = discord.Color.green()
                await interaction.response.edit_message(embed=embed, view=None)
                self.stop()
            else:
                # Ждем второго подтверждения
                embed = await self.trade_view.update_embed()
                await interaction.response.edit_message(embed=embed)
                
        @discord.ui.button(label="Отменить обмен", style=discord.ButtonStyle.red)
        async def cancel_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id not in [self.trade_view.initiator.id, self.trade_view.recipient.id]:
                await interaction.response.send_message("❌ Вы не участник этого обмена!", ephemeral=True)
                return
                
            embed = discord.Embed(
                title="❌ Обмен отменен",
                description=f"{interaction.user.mention} отменил обмен",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
    
    # Модальное окно для выбора предметов
    class ItemSelectModal(discord.ui.Modal):
        def __init__(self, trade_view: TradeView, is_initiator: bool):
            super().__init__(title="Выберите предметы для обмена")
            self.trade_view = trade_view
            self.is_initiator = is_initiator
            
            items = initiator_items if is_initiator else recipient_items
            for i, item in enumerate(items[:5]):  # Ограничение на 5 предметов для простоты
                self.add_item(discord.ui.TextInput(
                    label=f"Предмет {i+1}",
                    placeholder="Введите количество (0 для исключения)",
                    default="1",
                    required=False
                ))
                
        async def on_submit(self, interaction: discord.Interaction):
            items = initiator_items if self.is_initiator else recipient_items
            selected_items = []
            
            for i, item in enumerate(items[:5]):
                try:
                    count = int(self.children[i].value or "0")
                    if count > 0 and item in items:
                        selected_items.extend([item] * count)
                except ValueError:
                    pass
                    
            if self.is_initiator:
                self.trade_view.initiator_items = selected_items
            else:
                self.trade_view.recipient_items = selected_items
                
            embed = await self.trade_view.update_embed()
            await interaction.response.edit_message(embed=embed)
    
    # Модальное окно для выбора валюты
    class CurrencySelectModal(discord.ui.Modal):
        def __init__(self, trade_view: TradeView, is_initiator: bool):
            super().__init__(title="Выберите валюту для обмена")
            self.trade_view = trade_view
            self.is_initiator = is_initiator
            
            for currency in CURRENCIES:
                self.add_item(discord.ui.TextInput(
                    label=f"{currency} ({CURRENCIES[currency]})",
                    placeholder="Введите сумму (0 для исключения)",
                    default="0",
                    required=False
                ))
                
        async def on_submit(self, interaction: discord.Interaction):
            currency_dict = {}
            
            for i, currency in enumerate(CURRENCIES):
                try:
                    amount = int(self.children[i].value or "0")
                    if amount > 0:
                        # Проверяем баланс
                        balance = CurrencySystem.get_balance(
                            str(interaction.guild.id),
                            str(interaction.user.id),
                            currency
                        )
                        if balance < amount:
                            await interaction.response.send_message(
                                f"❌ Недостаточно {currency}! Ваш баланс: {balance}",
                                ephemeral=True
                            )
                            return
                        currency_dict[currency] = amount
                except ValueError:
                    pass
                    
            if self.is_initiator:
                self.trade_view.initiator_currency = currency_dict
            else:
                self.trade_view.recipient_currency = currency_dict
                
            embed = await self.trade_view.update_embed()
            await interaction.response.edit_message(embed=embed)
    
    # Отправляем начальное сообщение с кнопками
    setup_view = TradeSetupView(view)
    embed.set_footer(text="Используйте кнопки ниже для настройки обмена")
    await ctx.send(embed=embed, view=setup_view)

# ... (остальные команды add_item, remove_item и т.д. остаются без изменений)

bot.run(process.env.TOKEN)  # Замените на реальный токен
