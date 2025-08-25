from mirmod.utils.logger import logger
import mysql


def _create_metadata_entry(con, name, desc):
    try:
        cursor = con.cursor()
        # TODO user data not implemented
        sql = "INSERT INTO metadata (Created_by_id,Name,Description) VALUES (%s,%s,%s)"
        sql_data = (0, name, desc)
        cursor.execute(sql, sql_data)
        con.commit()
        metadata_id = cursor.lastrowid
        mystr = ("metadata added", metadata_id)
        logger.info(mystr)
        cursor.close()
        return metadata_id
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)


def _add_edge(con, src_type, dest_type, src, dest):
    """Introduce an edge between two metadata entries.
    @param src_type A string representation of the src type
    @param dest_type A string representation of the dest type
    @param src The metadata ID of the source
    @param dest The metadata ID of the destination
    """
    cursor = con.cursor()
    try:
        cursor.callproc("sp_link", [src_type, dest_type, src, dest])
    except Exception as err:
        logger.error("sp_link failed", err)
        raise mysql.connector.IntegrityError
    con.commit()
    for result in cursor.stored_results():
        _ = result.fetchall()
    edges_id = cursor.lastrowid
    cursor.close()
    return edges_id


def _remove_all_edges(con, id):
    try:
        cursor = con.cursor()
        sql = "DELETE FROM edges WHERE dest_type = %s or src_type = %s"
        sql_data = (id,)
        cursor.execute(sql, sql_data)
        con.commit()
        mystr = ("edges record(s) deleted", cursor.rowcount)
        logger.info(mystr)
        cursor.close()
    except mysql.connector.ProgrammingError as err:
        logger.error(err.msg)
    except mysql.connector.Error as err:
        logger.error(err)
