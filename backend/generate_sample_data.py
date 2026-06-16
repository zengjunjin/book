"""快速生成示例数据 - 书籍和评分"""
import sys
sys.path.insert(0, '.')

from app import create_app, db
from models import Book, User, Rating

app = create_app()

with app.app_context():
    # 1. 清空现有数据
    print("Clearing existing data...")
    db.session.query(Rating).delete()
    db.session.query(Book).delete()
    db.session.query(User).delete()
    db.session.commit()

    # 2. 插入示例书籍 (100本)
    sample_books = [
        {"isbn": "0195153448", "title": "Classical Mythology", "author": "Mark P. O. Morford", "year": 2002, "publisher": "Oxford University Press", "category": "History"},
        {"isbn": "0002005018", "title": "Clara Callan", "author": "Richard Bruce Wright", "year": 2001, "publisher": "HarperFlamingo Canada", "category": "Fiction"},
        {"isbn": "0060973129", "title": "Decision in Normandy", "author": "Carlo D'Este", "year": 1991, "publisher": "HarperPerennial", "category": "History"},
        {"isbn": "0374157065", "title": "Flu: The Story of the Great Influenza Pandemic of 1918 and the Search for the Virus That Caused It", "author": "Gina Kolata", "year": 1999, "publisher": "Farrar Straus Giroux", "category": "Science"},
        {"isbn": "0393045218", "title": "The Mummies of Urumchi", "author": "E. J. W. Barber", "year": 1999, "publisher": "W. W. Norton & Company", "category": "History"},
        {"isbn": "0399135782", "title": "The Kitchen God's Wife", "author": "Amy Tan", "year": 1991, "publisher": "Putnam Pub Group", "category": "Fiction"},
        {"isbn": "0425176428", "title": "What If?: The World's Foremost Military Historians Imagine What Might Have Been", "author": "Robert Cowley", "year": 2000, "publisher": "Berkley Publishing Group", "category": "History"},
        {"isbn": "0671870432", "title": "PLEADING GUILTY", "author": "Scott Turow", "year": 1993, "publisher": "Audiobook", "category": "Fiction"},
        {"isbn": "0679425608", "title": "Under the Black Flag: The Romance and the Reality of Life Among the Pirates", "author": "David Cordingly", "year": 1996, "publisher": "Random House", "category": "History"},
        {"isbn": "0743226755", "title": "Where You'll Find Me: And Other Stories", "author": "Ann Beattie", "year": 2002, "publisher": "Scribner", "category": "Fiction"},
        {"isbn": "0771074670", "title": "Nights Below Station Street", "author": "David Adams Richards", "year": 1988, "publisher": "Emblem Editions", "category": "Fiction"},
        {"isbn": "080652121X", "title": "Hitler's Secret Bankers: The Myth of Swiss Neutrality During the Holocaust", "author": "Adam Lebor", "year": 2000, "publisher": "Citadel Press", "category": "History"},
        {"isbn": "0887841740", "title": "The Middle Stories", "author": "Sheila Heti", "year": 2004, "publisher": "House of Anansi Press", "category": "Fiction"},
        {"isbn": "1552041778", "title": "Jane Doe", "author": "R. Barri Flowers", "year": 2005, "publisher": "Kensington Publishing Corp.", "category": "Mystery"},
        {"isbn": "1558746218", "title": "A Second Chicken Soup for the Woman's Soul", "author": "Jack Canfield", "year": 1998, "publisher": "Health Communications", "category": "Self-Help"},
        {"isbn": "1567407781", "title": "The Witchfinder (A Sister Frevisse Mystery)", "author": "Margaret Frazer", "year": 1998, "publisher": "Penguin USA", "category": "Mystery"},
        {"isbn": "1575663937", "title": "More Cunning Than Man: A Social History of Rats", "author": "Robert Sullivan", "year": 2001, "publisher": "The Lyons Press", "category": "Science"},
        {"isbn": "1881320189", "title": "Goodbye to the Buttermilk Sky", "author": "Julia Oliver", "year": 2001, "publisher": "River City Pub", "category": "Fiction"},
        {"isbn": "1885171276", "title": "The Weight of Water", "author": "Anita Shreve", "year": 2000, "publisher": "Back Bay Books", "category": "Fiction"},
        {"isbn": "2040000826", "title": "Liar", "author": "Jack M. Bickham", "year": 1999, "publisher": "Signet", "category": "Mystery"},
        {"isbn": "3257207526", "title": "Die Krone von Andoria. Roman.", "author": "Kilian Huber", "year": 1999, "publisher": "Heyne", "category": "Fiction"},
        {"isbn": "3257224281", "title": "The Catcher in the Rye", "author": "J. D. Salinger", "year": 1991, "publisher": "Little Brown", "category": "Fiction"},
        {"isbn": "3404619384", "title": "Darkly Dreaming Dexter", "author": "Jeff Lindsay", "year": 2004, "publisher": "Vintage Crime/Black Lizard", "category": "Mystery"},
        {"isbn": "3423113708", "title": "The Da Vinci Code", "author": "Dan Brown", "year": 2003, "publisher": "Doubleday", "category": "Fiction"},
        {"isbn": "3442355317", "title": "Angels & Demons", "author": "Dan Brown", "year": 2000, "publisher": "Pocket Books", "category": "Fiction"},
        {"isbn": "3492041412", "title": "Deception Point", "author": "Dan Brown", "year": 2001, "publisher": "Pocket Books", "category": "Fiction"},
        {"isbn": "3548258585", "title": "Digital Fortress", "author": "Dan Brown", "year": 1998, "publisher": "St. Martin's Griffin", "category": "Fiction"},
        {"isbn": "3598215963", "title": "The Lord of the Rings", "author": "J.R.R. Tolkien", "year": 2002, "publisher": "Houghton Mifflin Harcourt", "category": "Fiction"},
        {"isbn": "3807341880", "title": "The Hobbit", "author": "J.R.R. Tolkien", "year": 2002, "publisher": "Houghton Mifflin Harcourt", "category": "Fiction"},
        {"isbn": "4250821816", "title": "Harry Potter and the Sorcerer's Stone", "author": "J.K. Rowling", "year": 1998, "publisher": "Scholastic", "category": "Fiction"},
        {"isbn": "4250910314", "title": "Harry Potter and the Chamber of Secrets", "author": "J.K. Rowling", "year": 1999, "publisher": "Scholastic", "category": "Fiction"},
        {"isbn": "4390648642", "title": "Harry Potter and the Prisoner of Azkaban", "author": "J.K. Rowling", "year": 1999, "publisher": "Scholastic", "category": "Fiction"},
        {"isbn": "4391395970", "title": "Harry Potter and the Goblet of Fire", "author": "J.K. Rowling", "year": 2000, "publisher": "Scholastic", "category": "Fiction"},
        {"isbn": "43935806X", "title": "Harry Potter and the Order of the Phoenix", "author": "J.K. Rowling", "year": 2003, "publisher": "Scholastic", "category": "Fiction"},
        {"isbn": "4397859601", "title": "Harry Potter and the Half-Blood Prince", "author": "J.K. Rowling", "year": 2005, "publisher": "Scholastic", "category": "Fiction"},
        {"isbn": "4402301860", "title": "To Kill a Mockingbird", "author": "Harper Lee", "year": 1988, "publisher": "HarperPerennial", "category": "Fiction"},
        {"isbn": "4402329583", "title": "1984", "author": "George Orwell", "year": 1990, "publisher": "Secker & Warburg", "category": "Fiction"},
        {"isbn": "446310786", "title": "Animal Farm", "author": "George Orwell", "year": 1996, "publisher": "Signet Classic", "category": "Fiction"},
        {"isbn": "5535751041", "title": "11/22/63", "author": "Stephen King", "year": 2011, "publisher": "Scribner", "category": "Fiction"},
        {"isbn": "5535829155", "title": "The Shining", "author": "Stephen King", "year": 1977, "publisher": "Doubleday", "category": "Horror"},
        {"isbn": "5537626853", "title": "It", "author": "Stephen King", "year": 1986, "publisher": "Viking", "category": "Horror"},
        {"isbn": "609807305", "title": "The Stand", "author": "Stephen King", "year": 1990, "publisher": "Anchor", "category": "Fiction"},
        {"isbn": "6700306435", "title": "Carrie", "author": "Stephen King", "year": 1974, "publisher": "Doubleday", "category": "Horror"},
        {"isbn": "671042858", "title": "Pet Sematary", "author": "Stephen King", "year": 1983, "publisher": "Doubleday", "category": "Horror"},
        {"isbn": "679601406", "title": "Misery", "author": "Stephen King", "year": 1987, "publisher": "Viking", "category": "Horror"},
        {"isbn": "743273567", "title": "The Green Mile", "author": "Stephen King", "year": 1996, "publisher": "Pocket Books", "category": "Fiction"},
        {"isbn": "743465059", "title": "Duma Key", "author": "Stephen King", "year": 2008, "publisher": "Scribner", "category": "Horror"},
        {"isbn": "786818793", "title": "The Time Traveler's Wife", "author": "Audrey Niffenegger", "year": 2003, "publisher": "MacAdam/Cage Publishing", "category": "Fiction"},
        {"isbn": "8021237975", "title": "The Kite Runner", "author": "Khaled Hosseini", "year": 2003, "publisher": "Riverhead Books", "category": "Fiction"},
        {"isbn": "805080357", "title": "A Thousand Splendid Suns", "author": "Khaled Hosseini", "year": 2007, "publisher": "Riverhead Books", "category": "Fiction"},
        {"isbn": "8423479605", "title": "La Sombra del Viento", "author": "Carlos Ruiz Zafon", "year": 2001, "publisher": "Planeta", "category": "Fiction"},
        {"isbn": "8437620809", "title": "El Código Da Vinci", "author": "Dan Brown", "year": 2003, "publisher": "Doubleday", "category": "Fiction"},
        {"isbn": "8804357285", "title": "Il nome della rosa", "author": "Umberto Eco", "year": 1980, "publisher": "Bompiani", "category": "Mystery"},
        {"isbn": "9124158078", "title": "The Girl with the Dragon Tattoo", "author": "Stieg Larsson", "year": 2005, "publisher": "Norstedts Forlag", "category": "Mystery"},
        {"isbn": "954515535", "title": "The Girl Who Played with Fire", "author": "Stieg Larsson", "year": 2006, "publisher": "Quercus Publishing", "category": "Mystery"},
        {"isbn": "9780002247405", "title": "The Lord of the Rings: The Return of the King", "author": "J.R.R. Tolkien", "year": 2003, "publisher": "HarperCollins", "category": "Fiction"},
        {"isbn": "9780007112998", "title": "The Lord of the Rings: The Two Towers", "author": "J.R.R. Tolkien", "year": 1999, "publisher": "HarperCollins", "category": "Fiction"},
        {"isbn": "9780060168407", "title": "One Hundred Years of Solitude", "author": "Gabriel Garcia Marquez", "year": 1967, "publisher": "Harper & Row", "category": "Fiction"},
        {"isbn": "9780060524966", "title": "Love in the Time of Cholera", "author": "Gabriel Garcia Marquez", "year": 1985, "publisher": "Alfred A. Knopf", "category": "Fiction"},
        {"isbn": "9780060850524", "title": "Chronicle of a Death Foretold", "author": "Gabriel Garcia Marquez", "year": 1981, "publisher": "Alfred A. Knopf", "category": "Fiction"},
        {"isbn": "9780060934415", "title": "A Brief History of Time", "author": "Stephen Hawking", "year": 1988, "publisher": "Bantam", "category": "Science"},
        {"isbn": "9780061120084", "title": "The Universe in a Nutshell", "author": "Stephen Hawking", "year": 2001, "publisher": "Bantam", "category": "Science"},
        {"isbn": "9780091906818", "title": "Brave New World", "author": "Aldous Huxley", "year": 1932, "publisher": "Chatto & Windus", "category": "Fiction"},
        {"isbn": "9780140283295", "title": "Life of Pi", "author": "Yann Martel", "year": 2001, "publisher": "Knopf Canada", "category": "Fiction"},
        {"isbn": "9780140449136", "title": "The Grapes of Wrath", "author": "John Steinbeck", "year": 1939, "publisher": "The Viking Press", "category": "Fiction"},
        {"isbn": "9780141182551", "title": "Of Mice and Men", "author": "John Steinbeck", "year": 1937, "publisher": "Covici Friede", "category": "Fiction"},
        {"isbn": "9780141439600", "title": "Great Expectations", "author": "Charles Dickens", "year": 1861, "publisher": "Chapman & Hall", "category": "Fiction"},
        {"isbn": "9780141439846", "title": "A Tale of Two Cities", "author": "Charles Dickens", "year": 1859, "publisher": "Chapman & Hall", "category": "History"},
        {"isbn": "9780142437247", "title": "Oliver Twist", "author": "Charles Dickens", "year": 1838, "publisher": "Bentley", "category": "Fiction"},
        {"isbn": "9780192834072", "title": "Pride and Prejudice", "author": "Jane Austen", "year": 1813, "publisher": "T. Egerton", "category": "Fiction"},
        {"isbn": "9780199535569", "title": "Sense and Sensibility", "author": "Jane Austen", "year": 1811, "publisher": "T. Egerton", "category": "Fiction"},
        {"isbn": "9780199536603", "title": "Emma", "author": "Jane Austen", "year": 1815, "publisher": "John Murray", "category": "Fiction"},
        {"isbn": "9780307275431", "title": "The Road", "author": "Cormac McCarthy", "year": 2006, "publisher": "Alfred A. Knopf", "category": "Fiction"},
        {"isbn": "9780307277671", "title": "No Country for Old Men", "author": "Cormac McCarthy", "year": 2005, "publisher": "Alfred A. Knopf", "category": "Mystery"},
        {"isbn": "9780316015844", "title": "The Dark Tower I: The Gunslinger", "author": "Stephen King", "year": 1982, "publisher": "Grant", "category": "Fiction"},
        {"isbn": "9780316040754", "title": "The Dark Tower II: The Drawing of the Three", "author": "Stephen King", "year": 1987, "publisher": "Grant", "category": "Fiction"},
        {"isbn": "9780316069359", "title": "The Dark Tower III: The Waste Lands", "author": "Stephen King", "year": 1991, "publisher": "Grant", "category": "Fiction"},
        {"isbn": "9780316769174", "title": "The Catcher in the Rye", "author": "J.D. Salinger", "year": 1951, "publisher": "Little, Brown and Company", "category": "Fiction"},
        {"isbn": "9780316769488", "title": "Franny and Zooey", "author": "J.D. Salinger", "year": 1961, "publisher": "Little, Brown and Company", "category": "Fiction"},
        {"isbn": "9780374154067", "title": "The Corrections", "author": "Jonathan Franzen", "year": 2001, "publisher": "Farrar, Straus and Giroux", "category": "Fiction"},
        {"isbn": "9780374292799", "title": "Freedom", "author": "Jonathan Franzen", "year": 2010, "publisher": "Farrar, Straus and Giroux", "category": "Fiction"},
        {"isbn": "9780375508328", "title": "American Gods", "author": "Neil Gaiman", "year": 2001, "publisher": "William Morrow", "category": "Fiction"},
        {"isbn": "9780375714573", "title": "Neverwhere", "author": "Neil Gaiman", "year": 1996, "publisher": "BBC Books", "category": "Fiction"},
        {"isbn": "9780380789016", "title": "Coraline", "author": "Neil Gaiman", "year": 2002, "publisher": "HarperCollins", "category": "Fiction"},
        {"isbn": "9780385333405", "title": "The Stand", "author": "Stephen King", "year": 1978, "publisher": "Doubleday", "category": "Fiction"},
        {"isbn": "9780385472579", "title": "The Dark Half", "author": "Stephen King", "year": 1989, "publisher": "Viking", "category": "Horror"},
        {"isbn": "9780385504225", "title": "Bag of Bones", "author": "Stephen King", "year": 1998, "publisher": "Scribner", "category": "Horror"},
        {"isbn": "9780393058542", "title": "Moneyball: The Art of Winning an Unfair Game", "author": "Michael Lewis", "year": 2003, "publisher": "W. W. Norton & Company", "category": "Business"},
        {"isbn": "9780393324815", "title": "The Big Short", "author": "Michael Lewis", "year": 2010, "publisher": "W. W. Norton & Company", "category": "Business"},
        {"isbn": "9780399155345", "title": "Flash Boys", "author": "Michael Lewis", "year": 2014, "publisher": "W. W. Norton & Company", "category": "Business"},
        {"isbn": "9780425191163", "title": "The Firm", "author": "John Grisham", "year": 1991, "publisher": "Doubleday", "category": "Mystery"},
        {"isbn": "9780425199534", "title": "The Pelican Brief", "author": "John Grisham", "year": 1992, "publisher": "Doubleday", "category": "Mystery"},
        {"isbn": "9780425201602", "title": "The Client", "author": "John Grisham", "year": 1993, "publisher": "Doubleday", "category": "Mystery"},
        {"isbn": "9780425232223", "title": "The Rainmaker", "author": "John Grisham", "year": 1995, "publisher": "Doubleday", "category": "Mystery"},
        {"isbn": "9780425247999", "title": "The Runaway Jury", "author": "John Grisham", "year": 1996, "publisher": "Doubleday", "category": "Mystery"},
        {"isbn": "9780440176480", "title": "The Testament", "author": "John Grisham", "year": 1999, "publisher": "Doubleday", "category": "Mystery"},
        {"isbn": "9780440236016", "title": "The Partner", "author": "John Grisham", "year": 1997, "publisher": "Doubleday", "category": "Mystery"},
        {"isbn": "9780451167712", "title": "The Godfather", "author": "Mario Puzo", "year": 1969, "publisher": "G. P. Putnam's Sons", "category": "Fiction"},
        {"isbn": "9780451208637", "title": "The Sicilian", "author": "Mario Puzo", "year": 1984, "publisher": "Random House", "category": "Fiction"},
        {"isbn": "9780517107838", "title": "The Seven Habits of Highly Effective People", "author": "Stephen R. Covey", "year": 1989, "publisher": "Free Press", "category": "Self-Help"},
        {"isbn": "9780517149256", "title": "How to Win Friends and Influence People", "author": "Dale Carnegie", "year": 1936, "publisher": "Simon and Schuster", "category": "Self-Help"},
        {"isbn": "9780517200108", "title": "The Power of Positive Thinking", "author": "Norman Vincent Peale", "year": 1952, "publisher": "Prentice-Hall", "category": "Self-Help"},
        {"isbn": "9780547928227", "title": "The Hunger Games", "author": "Suzanne Collins", "year": 2008, "publisher": "Scholastic Press", "category": "Fiction"},
        {"isbn": "9780545227247", "title": "Catching Fire", "author": "Suzanne Collins", "year": 2009, "publisher": "Scholastic Press", "category": "Fiction"},
        {"isbn": "9780545227261", "title": "Mockingjay", "author": "Suzanne Collins", "year": 2010, "publisher": "Scholastic Press", "category": "Fiction"},
        {"isbn": "9780545010221", "title": "The Maze Runner", "author": "James Dashner", "year": 2009, "publisher": "Delacorte Press", "category": "Fiction"},
        {"isbn": "9780545139724", "title": "The Scorch Trials", "author": "James Dashner", "year": 2010, "publisher": "Delacorte Press", "category": "Fiction"},
        {"isbn": "9780545139731", "title": "The Death Cure", "author": "James Dashner", "year": 2011, "publisher": "Delacorte Press", "category": "Fiction"},
        {"isbn": "9780553213119", "title": "Dune", "author": "Frank Herbert", "year": 1965, "publisher": "Chilton Books", "category": "Science"},
        {"isbn": "9780553292992", "title": "Foundation", "author": "Isaac Asimov", "year": 1951, "publisher": "Gnome Press", "category": "Science"},
        {"isbn": "9780553293364", "title": "I, Robot", "author": "Isaac Asimov", "year": 1950, "publisher": "Gnome Press", "category": "Science"},
        {"isbn": "9780553382563", "title": "Neuromancer", "author": "William Gibson", "year": 1984, "publisher": "Ace Books", "category": "Science"},
        {"isbn": "9780553573404", "title": "Snow Crash", "author": "Neal Stephenson", "year": 1992, "publisher": "Bantam Spectra", "category": "Science"},
        {"isbn": "9780553804362", "title": "Cryptonomicon", "author": "Neal Stephenson", "year": 1999, "publisher": "Avon", "category": "Science"},
        {"isbn": "9780618002220", "title": "The Hobbit: Or There and Back Again", "author": "J.R.R. Tolkien", "year": 1937, "publisher": "George Allen & Unwin", "category": "Fiction"},
        {"isbn": "9780618260300", "title": "The Silmarillion", "author": "J.R.R. Tolkien", "year": 1977, "publisher": "George Allen & Unwin", "category": "Fiction"},
        {"isbn": "9780670020577", "title": "A Game of Thrones", "author": "George R.R. Martin", "year": 1996, "publisher": "Bantam Spectra", "category": "Fiction"},
        {"isbn": "9780670032609", "title": "A Clash of Kings", "author": "George R.R. Martin", "year": 1998, "publisher": "Bantam Spectra", "category": "Fiction"},
        {"isbn": "9780671004101", "title": "A Storm of Swords", "author": "George R.R. Martin", "year": 2000, "publisher": "Bantam Spectra", "category": "Fiction"},
        {"isbn": "9780765311788", "title": "A Feast for Crows", "author": "George R.R. Martin", "year": 2005, "publisher": "Bantam Spectra", "category": "Fiction"},
        {"isbn": "9780765312969", "title": "A Dance with Dragons", "author": "George R.R. Martin", "year": 2011, "publisher": "Bantam Spectra", "category": "Fiction"},
        {"isbn": "9780786838653", "title": "The Five People You Meet in Heaven", "author": "Mitch Albom", "year": 2003, "publisher": "Hyperion", "category": "Fiction"},
        {"isbn": "9780786868414", "title": "Tuesdays with Morrie", "author": "Mitch Albom", "year": 1997, "publisher": "Doubleday", "category": "Self-Help"},
        {"isbn": "9780802144751", "title": "The Wind-Up Bird Chronicle", "author": "Haruki Murakami", "year": 1994, "publisher": "Shinchosha", "category": "Fiction"},
        {"isbn": "9780812977999", "title": "Norwegian Wood", "author": "Haruki Murakami", "year": 1987, "publisher": "Kodansha", "category": "Fiction"},
        {"isbn": "9781400033416", "title": "Kafka on the Shore", "author": "Haruki Murakami", "year": 2002, "publisher": "Shinchosha", "category": "Fiction"},
        {"isbn": "9781400096190", "title": "1Q84", "author": "Haruki Murakami", "year": 2009, "publisher": "Shinchosha", "category": "Fiction"},
        {"isbn": "9781848549054", "title": "The Martian", "author": "Andy Weir", "year": 2011, "publisher": "Crown Publishing Group", "category": "Science"},
        {"isbn": "9781594630810", "title": "The Night Circus", "author": "Erin Morgenstern", "year": 2011, "publisher": "Doubleday", "category": "Fiction"},
        {"isbn": "9781616201341", "title": "The Underground Railroad", "author": "Colson Whitehead", "year": 2016, "publisher": "Doubleday", "category": "Fiction"},
    ]

    print(f"Inserting {len(sample_books)} books...")
    for b in sample_books:
        book = Book(**b)
        db.session.add(book)
    db.session.commit()
    print(f"Books inserted: {Book.query.count()}")

    # 3. 创建一些用户
    print("Creating sample users...")
    users = []
    for i in range(1, 30):
        u = User(username=f"user_{i}", email=f"user{i}@example.com")
        u.set_password("password123")
        db.session.add(u)
        users.append(u)
    db.session.commit()
    print(f"Users created: {User.query.count()}")

    # 4. 生成评分 (模拟用户兴趣分组)
    import random
    random.seed(42)

    books = Book.query.all()
    users = User.query.all()

    # 定义用户偏好分组 (某些用户偏爱某类书)
    preferences = {
        "fiction_users": ["Fiction"],
        "mystery_users": ["Mystery"],
        "scifi_users": ["Science"],
        "history_users": ["History"],
        "mixed_users": ["Fiction", "Mystery", "Science"]
    }

    print("Generating sample ratings...")
    rating_count = 0

    for idx, user in enumerate(users):
        # 根据用户idx分配偏好
        if idx < 6:
            pref_cats = ["Fiction"]
        elif idx < 12:
            pref_cats = ["Mystery"]
        elif idx < 18:
            pref_cats = ["Science"]
        elif idx < 24:
            pref_cats = ["History"]
        else:
            pref_cats = ["Fiction", "Mystery", "Science", "Horror"]

        # 用户评分的书籍 (每用户评分15-25本)
        rated_count = random.randint(15, 25)

        # 优先选择偏好分类的书
        preferred_books = [b for b in books if b.category in pref_cats]
        other_books = [b for b in books if b.category not in pref_cats]

        # 80% 偏好分类书籍, 20%其他
        preferred_count = int(rated_count * 0.8)
        other_count = rated_count - preferred_count

        selected_books = random.sample(preferred_books, min(preferred_count, len(preferred_books)))
        if other_books and other_count > 0:
            selected_books += random.sample(other_books, min(other_count, len(other_books)))

        for book in selected_books:
            # 偏好的书给高分(7-10), 其他给低分(3-7)
            if book.category in pref_cats:
                score = random.randint(7, 10)
            else:
                score = random.randint(3, 7)

            rating = Rating(user_id=user.id, book_id=book.id, rating=score)
            db.session.add(rating)
            rating_count += 1

        # 每10个用户提交一次, 避免内存问题
        if idx % 10 == 0:
            db.session.commit()

    db.session.commit()
    print(f"Ratings inserted: {Rating.query.count()}")

    print("\n=== Data Summary ===")
    print(f"Total Books: {Book.query.count()}")
    print(f"Total Users: {User.query.count()}")
    print(f"Total Ratings: {Rating.query.count()}")

    # 统计各分类
    from sqlalchemy import func
    results = db.session.query(Book.category, func.count(Book.id)).group_by(Book.category).all()
    print("\nBooks by category:")
    for cat, cnt in results:
        print(f"  {cat}: {cnt}")

    # 评分分布
    results = db.session.query(Rating.rating, func.count(Rating.id)).group_by(Rating.rating).order_by(Rating.rating).all()
    print("\nRating distribution:")
    for score, cnt in results:
        bar = '#' * (cnt // 20)
        print(f"  {score}: {cnt} {bar}")

    print("\n=== Sample data inserted successfully! ===")
    print("You can now login with any username (user_1 to user_29) and password 'password123'")
