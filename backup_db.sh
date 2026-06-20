#!/bin/bash
# backup_db.sh - Sauvegarde la base de donnees TalibDrive avant toute migration

mkdir -p backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [ -f talibdrive.db ]; then
    cp talibdrive.db "backups/talibdrive_${TIMESTAMP}.db"
    echo "Backup cree: backups/talibdrive_${TIMESTAMP}.db"
else
    echo "Aucune base de donnees trouvee a sauvegarder."
fi
