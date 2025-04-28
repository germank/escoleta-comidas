import calendar
import random
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
import json
import yaml
import locale
locale.setlocale(locale.LC_ALL, 'ca_ES')
import calendar
import json
import random
from collections import defaultdict, deque
from PIL import Image, ImageDraw, ImageFont

def load_config(filename="config.yml"):
    try:
        with open(filename, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def generate_schedule(kids, unavailability, fixed, weekday_constraints, past_allocations, year, month, closed_days):
    days_in_month = calendar.monthrange(year, month)[1]
    schedule = {}
    fairness_score = defaultdict(int, past_allocations.get("fairness", {}))
    recency_queue = deque(past_allocations.get("recency", []), maxlen=len(kids) * 5)  # Track recent allocations
    week_allocations = defaultdict(set)  # Track allocations per week
    
    # Default availability is the entire month
    full_month = set(range(1, days_in_month + 1))
    availability = {kid: full_month - set(unavailability.get(kid, [])) for kid in kids}
    
    for day in range(1, days_in_month + 1):
        if day in closed_days:
            schedule[day] = "TANCAT"
            continue
        
        weekday = calendar.weekday(year, month, day) + 1
        week_num = (day + calendar.monthrange(year, month)[0] - 1) // 7  # Determine the week number
        fixed_families_for_day = [kid for kid in fixed if day in fixed[kid]]
        assert len(fixed_families_for_day) <= 1, f"No se puede asignar más de una familia a un día. Hay {fixed_families_for_day} para el día {day}."
        if fixed_families_for_day:
            eligible_kids = fixed_families_for_day
        else:
            eligible_kids = [kid for kid in kids if day in availability[kid] and weekday in weekday_constraints.get(kid, set(range(1, 5+1))) and kid not in week_allocations[week_num]]
        
        if eligible_kids:
            # Sort first by fairness score, then by recency (least recently allocated first)
            kid = min(eligible_kids, key=lambda k: (fairness_score[k], recency_queue.index(k) if k in recency_queue else -1))
            print(f'scheduling {kid} to day {day} with fairness score {fairness_score[kid]} and recency index {recency_queue.index(kid) if kid in recency_queue else -1}')
            if kid in recency_queue and recency_queue.index(kid) > 0:
                first_in_queue=recency_queue[0]
                print(f"{kid} went ahead of {first_in_queue} with fairness score {fairness_score[first_in_queue]}")
            schedule[day] = kid
            fairness_score[kid] += 1  # Increase fairness score after allocation
            if kid in recency_queue:
                recency_queue.remove(kid)
            recency_queue.append(kid)  # Track recent allocations
            week_allocations[week_num].add(kid)  # Mark kid as allocated for this week
    
    return schedule, {"fairness": fairness_score, "recency": list(recency_queue)}

def save_allocations(fairness_score, year, month):
    filename = f"allocations_{year}_{month}.json"
    with open(filename, "w") as f:
        json.dump(fairness_score, f)

def load_allocations(year, month):
    filename = f"allocations_{year}_{month}.json"
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def render_calendar(schedule, year, month):
    width, height = 900, 700
    vertical_offset = 0
    try:
        background = Image.open("fondo.png").resize((width, height)).convert("RGBA")
    except IOError:
        background = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    
    overlay = Image.new("RGBA", (width, height), (255, 255, 255, 180))  # Semi-transparent overlay
    img = Image.alpha_composite(background, overlay)
    draw = ImageDraw.Draw(img)    
    try:
        font = ImageFont.truetype("Arial.ttf", 24)  # Modern and smooth font
        bold_font = ImageFont.truetype("Arial Bold.ttf", 22)  # Modern and smooth font
        small_font = ImageFont.truetype("Arial.ttf", 18)  # Modern and smooth font
    except IOError:
        print('Error Loading font')
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    title = f"Calendario de Comidas - {calendar.month_name[month]} {year}"
    draw.text((width//4, vertical_offset), title, fill="black", font=font)
    
    days_in_month = calendar.monthrange(year, month)[1]
    first_weekday = calendar.monthrange(year, month)[0]
    cell_width = width // 7
    cell_height = (height - 100) // 6
    
    for i in range(7):
        draw.text((i * cell_width + 30, vertical_offset + 30), calendar.day_abbr[i], fill="black", font=font)
    
    for day in range(1, days_in_month + 1):
        row = (first_weekday + day - 1) // 7
        col = (first_weekday + day - 1) % 7
        x = col * cell_width
        y = row * cell_height + 100 + vertical_offset
        draw.rectangle([x, y, x + cell_width, y + cell_height], outline="black")
        draw.text((x + 15, y + 5), str(day), fill="black", font=font)
        if day in schedule:
            draw.text((x + cell_width // 4 - 5, y + cell_height // 3), schedule[day], fill="black", font=bold_font)
            if schedule[day] != "TANCAT" and col < 5:
                draw.text((x + cell_width // 4 - 5, y + cell_height // 3 + 40), f"(pack {col+1})", fill="black", font=small_font)
    
    img = img.convert("RGB")  # Convert back to RGB for saving
    img.save(f"calendario_{year}_{month}.png")
    img.show()

def main():
    config = load_config()
    year, month = config.get("year", 2024), config.get("month", 3)
    kids = config.get("kids", [])
    unavailability = config.get("unavailability", {})
    if unavailability is None:
        unavailability = {}
    fixed = config.get("fixed", {})
    if fixed is None:
        fixed = {}
    weekday_constraints = config.get("weekday_constraints", {})
    closed_days = set(config.get("closed_days", []))

    past_allocations = load_allocations(year, month - 1 if month > 1 else 12)  # Load past month allocations
    for k in kids:
        if k not in past_allocations['fairness']:
            past_allocations['fairness'][k] = max(past_allocations['fairness'].values()) # start with the best score
            past_allocations['recency'].append(k) # Begins at the end of the round

    schedule, updated_allocations = generate_schedule(kids, unavailability, fixed, weekday_constraints, past_allocations, year, month, closed_days)
    updated_allocations['schedule'] = schedule
    save_allocations(updated_allocations, year, month)
    render_calendar(schedule, year, month)

if __name__ == "__main__":
    main()

