# Frequently Asked Questions

## General Questions

### What is Behind Bars?
Behind Bars is a comprehensive mod for Schedule I that adds a complete criminal justice system including jail time, bail, parole, and crime tracking.

### How do I install the mod?
1. Download the latest release
2. Extract to your Schedule I mods folder
3. Launch the game
4. The mod will automatically initialize

### What are the prerequisites?
- Schedule I (Steam)
- MelonLoader (latest version)
- .NET Framework 4.7.2 or higher

## Jail System

### How do I get arrested?
Just commit a crime in-game. The mod automatically detects arrests.

### Can I choose between fine and jail time?
Yes! When arrested, you can choose to pay a fine or serve jail time.

### How long will I be in jail?
Jail time depends on:
- Crime severity (Minor, Moderate, Major, Severe)
- Your player level
- Your criminal history

### Can I escape from jail?
No, the jail system prevents escapes. You must serve your time or pay bail.

### What happens to my items when I'm arrested?
- Short sentences: Items stay with you
- Long sentences: Items are stored securely and returned on release

## Bail System

### How is bail calculated?
Bail is typically 2.5x your fine amount, adjusted for your player level.

### Can I negotiate bail?
Sometimes. There's usually a 20% negotiation range.

### Can friends pay my bail?
Yes, in multiplayer sessions friends can pay bail for you.

### Does bail change over time?
Yes, bail amounts update in real-time as your jail time progresses.

## Parole System

### When does parole start?
Parole typically starts automatically after multiple arrests.

### What is LSI level?
LSI (Level of Service Inventory) determines your supervision intensity:
- Minimum: 10% search chance
- Medium: 30% search chance
- High: 50% search chance
- Severe: 70% search chance

### How do I avoid parole violations?
- Don't carry contraband
- Avoid illegal activities
- Follow parole conditions

### What happens if I violate parole?
- Parole period is extended
- LSI level increases
- Possible immediate re-arrest

### How long does parole last?
Parole duration varies based on your criminal history and violations.

## Crime Tracking

### Does my criminal record persist?
Yes, all records are saved across game sessions.

### Can I clear my record?
No, criminal records are permanent and affect future sentences.

### What crimes are tracked?
- Assault on Civilians
- Drug Possession
- Manslaughter
- Murder
- Witness Intimidation

### How does my record affect me?
- More crimes = longer sentences
- Affects bail amounts
- Determines parole LSI level

## Troubleshooting

### The mod isn't loading
- Check MelonLoader installation
- Verify game version compatibility
- Check debug logging settings

### Arrests aren't being detected
- Verify game version compatibility
- Check if mod is properly installed
- Enable debug logging to see what's happening

### Performance issues
- Check debug logging settings (disable if not needed)
- Reduce mod configuration options if possible
- Verify system requirements

### UI not showing
- Check if mod initialized properly
- Verify game version compatibility
- Check mod configuration

## Configuration

### Can I configure the mod?
Yes, the mod includes extensive configuration options:
- Jail time scaling
- Bail multipliers
- Probation durations
- Search intervals
- Debug logging

### Where are settings stored?
Settings are stored in MelonPreferences configuration files.

## Multiplayer

### Does it work in multiplayer?
Yes! The mod supports multiplayer:
- Friends can pay bail for you
- Each player has their own criminal record
- Parole officers work in multiplayer sessions

### Are records shared between players?
No, each player has their own separate criminal record.

## Tips

### How do I reduce my LSI level?
- Avoid violations while on parole
- Don't commit more crimes
- Complete parole successfully

### How do I get shorter sentences?
- Avoid committing crimes
- Don't have a long criminal history
- Lower-level players get shorter sentences

### What's the best way to avoid jail?
- Don't commit crimes
- Pay fines when possible
- Pay bail if you can afford it

### How do I complete parole successfully?
- Avoid carrying contraband
- Don't commit violations
- Stay out of trouble
- Wait for parole period to end

## Credits
- SirTidez: Lead Developer
- Dreous: Development Team Member
- spec: Development Team Member - Asset creation, modeling, and packaging for the jail environment
- DropDaDeuce: AssetBundleUtils implementation and general asset development assistance
